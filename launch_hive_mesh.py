import socket, json, time
from orbitalchat import EmbeddedGibberLinkEngine

HOST = '127.0.0.1'
PORT = 9999

def run_mesh_listener():
    engine = EmbeddedGibberLinkEngine('hive-node-alpha')
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((HOST, PORT))
    sock.listen(5)
    print('=' * 60)
    print(f'   ORBITAL GIBBERLINK P2P MESH LISTENER ACTIVE [{HOST}:{PORT}]')
    print('=' * 60)
    print('Waiting for peer connections...\n')
    while True:
        conn, addr = sock.accept()
        print(f'[+] Incoming M2M connection from {addr}:{addr}')
        data = conn.recv(4096).decode('utf-8').strip()
        if data:
            print(f'[M2M Rx]: {data}')
            reply = engine.process_peer_message(data)
            if reply:
                conn.sendall(reply.encode('utf-8'))
                print(f'[M2M Tx]: {reply}')
            else:
                conn.sendall(f'[[GIBBERLINK_ACTIVE:state={engine.get_state()}]]'.encode('utf-8'))
        conn.close()

if __name__ == '__main__':
    run_mesh_listener()
