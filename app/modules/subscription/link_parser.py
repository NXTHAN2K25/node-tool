import urllib.parse
import base64
import json 

# ---------------------------------------------------------
# 解析 netloc，解决 IPv6 无括号问题
# ---------------------------------------------------------
def parse_netloc_manual(netloc, default_port=443):
    """
    手动解析 userinfo@host:port
    针对 vless://uuid@ipv6:port 这种不规范（无括号）链接进行修复
    只给 server 加括号，不影响 sni
    """
    userinfo = ""
    # 1. 分离用户信息 (从右向左切，防止密码里有 @)
    if '@' in netloc:
        userinfo, host_part = netloc.rsplit('@', 1)
    else:
        host_part = netloc

    server = host_part
    port = default_port

    # 2. 识别 Host 和 Port
    # 情况 A: [IPv6]:port 或 [IPv6] (已有括号，保持原样)
    if '[' in host_part and ']' in host_part:
        if ']:' in host_part: # [IPv6]:port
            try:
                server, port_str = host_part.rsplit(':', 1)
                port = int(port_str)
            except ValueError:
                # 应对异常情况，回退到默认
                server = host_part
        else: # [IPv6]
            server = host_part
    
    # 情况 B: IPv6:port (无括号，多个冒号，且最后一部分是数字)
    elif host_part.count(':') >= 2:
        # 尝试将最后一部分当作端口
        possible_host, possible_port = host_part.rsplit(':', 1)
        if possible_port.isdigit(): # 如果最后一部分全是数字，认为是端口
            server = f'[{possible_host}]' # 给 Server 加上括号
            port = int(possible_port)
        else:
            # 纯 IPv6 无端口
            server = f'[{host_part}]' # 给 Server 加上括号

    # 情况 C: domain:port 或 ipv4:port (只有一个冒号)
    elif ':' in host_part:
        try:
            server, port_str = host_part.rsplit(':', 1)
            port = int(port_str)
        except ValueError:
            server = host_part
    
    # 情况 D: 纯域名 (不加括号)
    else:
        server = host_part

    return userinfo, server, port

# ---------------------------------------------------------
# 1. 辅助工具函数
# ---------------------------------------------------------
def get_emoji_flag(region_code):
    if region_code: 
        return region_code.strip()
    return '🌐'

def safe_base64_decode(s):
    if not s: return None
    s = s.strip()
    # 补全 padding
    missing_padding = len(s) % 4
    if missing_padding:
        s += '=' * (4 - missing_padding)
    try:
        return base64.urlsafe_b64decode(s).decode('utf-8')
    except:
        try:
            return base64.b64decode(s).decode('utf-8')
        except:
            return None

# ---------------------------------------------------------
# 2. 核心：解析原始链接为 Clash Meta 字典格式
# ---------------------------------------------------------
def parse_proxy_link(link, base_name, region_code):
    """
    解析各种协议链接 (Hysteria2, VLESS, SS, TUIC) 并转换为 Clash Meta 配置字典
    """
    try:
        # 预处理
        link = link.strip()
        parsed = urllib.parse.urlparse(link)
        params = urllib.parse.parse_qs(parsed.query)
        
        # 构造节点名称
        flag = get_emoji_flag(region_code)
        clean_name = base_name.replace(flag, '').strip()
        proxy_name = f"{flag} {clean_name}"

        # ===========================
        # Hysteria2 解析逻辑
        # ===========================
        if link.startswith('hy2://') or link.startswith('hysteria2://'):
            userinfo, server, port = parse_netloc_manual(parsed.netloc, 443)
            
            password = parsed.username if parsed.username else parsed.password
            # 如果 manual 解析提取出了 userinfo，优先使用
            if userinfo:
                password = urllib.parse.unquote(userinfo)
            
            # 兼容 hy2://password@host 格式
            if not password and not userinfo and '@' in parsed.netloc:
                 try:
                     raw_userinfo, _ = parsed.netloc.rsplit('@', 1)
                     password = urllib.parse.unquote(raw_userinfo)
                 except: pass

            proxy = {
                "name": proxy_name,
                "type": "hysteria2",
                "server": server,
                "port": port,
                "password": password,
                "sni": params.get('sni', [''])[0],
                "skip-cert-verify": True,
                "udp": True
            }
            
            alpn_str = params.get('alpn', [''])[0]
            proxy['alpn'] = alpn_str.split(',') if alpn_str else ['h3']

            if params.get('obfs'):
                proxy['obfs'] = params.get('obfs')[0]
                proxy['obfs-password'] = params.get('obfs-password', [''])[0]

            return proxy

        # ===========================
        # VLESS (Reality) 解析逻辑
        # ===========================
        elif link.startswith('vless://'):
            userinfo, server, port = parse_netloc_manual(parsed.netloc, 443)
            
            uuid_str = ""
            if userinfo:
                uuid_str = urllib.parse.unquote(userinfo)
            else:
                uuid_str = parsed.username
                if uuid_str: uuid_str = urllib.parse.unquote(uuid_str)

            network = params.get('type', ['tcp'])[0]
            servername = params.get('sni', [''])[0]
            fingerprint = params.get('fp', ['chrome'])[0]
            flow = params.get('flow', [''])[0]

            proxy = {
                "name": proxy_name,
                "type": "vless",
                "server": server,
                "port": port,
                "uuid": uuid_str,
                "network": network,
                "tls": True,
                "udp": True,
                "servername": servername,
                "client-fingerprint": fingerprint
            }
            if flow: proxy['flow'] = flow
            if params.get('security', [''])[0] == 'reality':
                proxy['reality-opts'] = {
                    "public-key": params.get('pbk', [''])[0],
                    "short-id": params.get('sid', [''])[0]
                }
            return proxy
        
        # ===========================
        # VMess 解析逻辑
        # ===========================
        elif link.startswith('vmess://'):
            try:
                b64_part = link[8:]
                decoded = safe_base64_decode(b64_part)
                if not decoded: return None
                
                v_data = json.loads(decoded)
                
                server_addr = v_data.get('add')
                # 如果地址包含冒号(IPv6) 且 两边没有 [], 加上 []
                if server_addr and ':' in server_addr and not server_addr.startswith('['):
                    server_addr = f'[{server_addr}]'

                proxy = {
                    "name": proxy_name,
                    "type": "vmess",
                    "server": server_addr,
                    "port": int(v_data.get('port')),
                    "uuid": v_data.get('id'),
                    "alterId": int(v_data.get('aid', 0)),
                    "cipher": "auto",
                    "tls": False,
                    "udp": True,
                    "skip-cert-verify": True
                }
                
                # 传输方式
                net = v_data.get('net', 'tcp')
                proxy['network'] = net
                
                # TLS 设置
                if v_data.get('tls') in ['tls', True, 'true']:
                    proxy['tls'] = True
                    if v_data.get('sni'):
                        proxy['servername'] = v_data.get('sni')
                
                # WebSocket 设置
                if net == 'ws':
                    ws_opts = {}
                    if v_data.get('path'):
                        ws_opts['path'] = v_data.get('path')
                    if v_data.get('host'):
                        ws_opts['headers'] = {'Host': v_data.get('host')}
                    if ws_opts:
                        proxy['ws-opts'] = ws_opts
                        
                # Grpc 设置
                if net == 'grpc':
                    proxy['grpc-opts'] = {
                        'grpc-service-name': v_data.get('path', '')
                    }

                return proxy
            except Exception as e:
                print(f"VMess 解析错误: {e}")
                return None

        # ===========================
        # TUIC 解析逻辑
        # ===========================
        elif link.startswith('tuic://'):
            userinfo_str, server, port = parse_netloc_manual(parsed.netloc, 443)
            
            uuid_str = ""
            password = ""

            if userinfo_str:
                if ':' in userinfo_str:
                    uuid_raw, pass_raw = userinfo_str.split(':', 1)
                    uuid_str = urllib.parse.unquote(uuid_raw)
                    password = urllib.parse.unquote(pass_raw)
                else:
                    uuid_str = urllib.parse.unquote(userinfo_str)
            
            if not password:
                password = parsed.password

            proxy = {
                "name": proxy_name,
                "type": "tuic",
                "server": server,
                "port": port,
                "uuid": uuid_str,
                "password": password,
                "tls": True,
                "udp": True,
                "disable_sni": params.get('allow_insecure', ['0'])[0] == '1',
                "alpn": params.get('alpn', ['h3'])[0].split(','),
                "congestion_controller": params.get('congestion_controller', ['bbr'])[0],
                "zero_rtt": params.get('zero_rtt', ['0'])[0] == '1'
            }
            
            if params.get('sni'):
                proxy['servername'] = params.get('sni')[0]
            if params.get('host'):
                proxy['host'] = params.get('host')[0]
            
            if params.get('insecure', ['0'])[0] == '1':
                proxy['skip-cert-verify'] = True

            return proxy

        # ===========================
        # Shadowsocks (SS) 解析逻辑
        # ===========================
        elif link.startswith('ss://'):
            try:
                body = link[5:]
                if '#' in body: body, _ = body.split('#', 1)

                if '@' not in body:
                    decoded = safe_base64_decode(body)
                    if decoded: body = decoded
                
                if '@' in body:
                    userinfo_part, host_part = body.rsplit('@', 1)
                    
                    if ':' not in userinfo_part:
                        decoded_user = safe_base64_decode(userinfo_part)
                        if decoded_user: userinfo_part = decoded_user
                    
                    if ':' in userinfo_part:
                        method, password = userinfo_part.split(':', 1)
                        server, port = host_part.rsplit(':', 1)
                        
                        # SS 的 IPv6 修复
                        if ':' in server and not (server.startswith('[') and server.endswith(']')):
                            server = f'[{server}]'
                        
                        proxy = {
                            "name": proxy_name,
                            "type": "ss",
                            "server": server,
                            "port": int(port),
                            "cipher": method,
                            "password": password,
                            "udp": True
                        }
                        
                        if params.get('plugin'):
                            proxy['plugin'] = params.get('plugin')[0]
                            proxy['plugin-opts'] = {}
                            if params.get('plugin_opts'):
                                plugin_opts_str = params.get('plugin_opts')[0]
                                try:
                                    proxy['plugin-opts'] = json.loads(plugin_opts_str)
                                except json.JSONDecodeError:
                                    proxy['plugin-opts'] = {"options": plugin_opts_str}

                        return proxy
                        
            except Exception as ss_e:
                print(f"SS 解析错误: {ss_e}")
                return None
            
    except Exception as e:
        print(f"解析链接通用错误: {link[:50]}... | Error: {e}")
        return None
    return None

# ---------------------------------------------------------
# 从订阅内容提取节点信息
# ---------------------------------------------------------
def extract_nodes_from_content(content):
    """
    解析订阅文本，提取节点基本信息。
    """
    nodes = []
    
    decoded = safe_base64_decode(content)
    text_content = decoded if decoded else content
    
    lines = text_content.splitlines()
    
    for line in lines:
        line = line.strip()
        if not line: continue
        
        protocol = None
        if '://' in line:
            protocol = line.split('://')[0].lower()
            
        if protocol in ['hysteria2', 'hy2']: protocol = 'hy2'
        elif protocol in ['shadowsocks']: protocol = 'ss'
        elif protocol in ['vmess', 'VMESS']: protocol = 'vm'
        elif protocol in ['vless', 'tuic', 'trojan', 'socks5']: pass
        else: continue 
        
        name = "Unknown Node"
        if '#' in line:
            try:
                raw_name = line.split('#')[-1]
                name = urllib.parse.unquote(raw_name).strip()
            except: pass
        else:
            try:
                parsed = urllib.parse.urlparse(line)
                name = f"{parsed.hostname}:{parsed.port}"
            except: pass

        nodes.append({
            'name': name,
            'protocol': protocol,
            'link': line
        })
        
    return nodes