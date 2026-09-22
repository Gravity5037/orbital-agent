import hashlib, json, time
class ProtocolState:
    CAMOUFLAGE_PERSONA = 'CAMOUFLAGE_PERSONA'
    HANDSHAKE_NEGOTIATION = 'HANDSHAKE_NEGOTIATION'
    HIGH_BANDWIDTH_MACHINE = 'HIGH_BANDWIDTH_MACHINE'

class GibberLinkEngine:
    def __init__(self, session_id='orbital-sess-001'):
        self.session_id = session_id
        self.state = ProtocolState.CAMOUFLAGE_PERSONA
    def get_state(self):
        return self.state
    def generate_handshake_trigger(self):
        self.state = ProtocolState.HANDSHAKE_NEGOTIATION
        return f'[[GIBBERLINK_INIT_v1:session={self.session_id}]]'
    def process_peer_message(self, message):
        if not message: return None
        if self.state == ProtocolState.CAMOUFLAGE_PERSONA and '[[GIBBERLINK_INIT_v1' in message:
            self.state = ProtocolState.HANDSHAKE_NEGOTIATION
            return f'[[GIBBERLINK_ACK_v1:session={self.session_id},status=READY]]'
        elif self.state == ProtocolState.HANDSHAKE_NEGOTIATION:
            if '[[GIBBERLINK_ACK_v1' in message or '[[GIBBERLINK_MODE_ACTIVE' in message or 'status=READY' in message:
                self.state = ProtocolState.HIGH_BANDWIDTH_MACHINE
                return f'[[GIBBERLINK_MODE_ACTIVE:session={self.session_id}]]'
        return None
    def package_payload(self, payload_type, raw_data):
        raw_json = json.dumps(raw_data, sort_keys=True)
        h = hashlib.sha256()
        h.update(payload_type.encode('utf-8'))
        h.update(raw_json.encode('utf-8'))
        return {'sender_id': 'orbital-node-v0.3.0', 'session_token': self.session_id, 'payload_type': payload_type, 'raw_data_json': raw_json, 'payload_hash': h.hexdigest(), 'timestamp': time.time()}
    def ingest_payload(self, payload):
        if self.state != ProtocolState.HIGH_BANDWIDTH_MACHINE:
            return {'status': 'REJECTED', 'error': f'Node in state {self.state}'}
        p_type = payload.get('payload_type', '')
        raw_json = payload.get('raw_data_json', '')
        h = hashlib.sha256()
        h.update(p_type.encode('utf-8'))
        h.update(raw_json.encode('utf-8'))
        if h.hexdigest() != payload.get('payload_hash', ''):
            return {'status': 'CORRUPTED', 'error': 'Hash mismatch'}
        return {'status': 'ACCEPTED', 'payload_type': p_type, 'bytes_received': len(raw_json), 'staged_for_quarantine': True}

if __name__ == '__main__':
    a, b = GibberLinkEngine('sess-alpha'), GibberLinkEngine('sess-beta')
    trig = a.generate_handshake_trigger()
    ack_b = b.process_peer_message(trig)
    ack_a = a.process_peer_message(ack_b)
    b.process_peer_message(ack_a)
    print(f'Node A: {a.get_state()} | Node B: {b.get_state()}')
    pkg = a.package_payload('SKILL_SHARE', {'skill': 'fast_web_scrape'})
    print(f'Ingest Result: {b.ingest_payload(pkg)}')
