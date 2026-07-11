import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017')

import server


def test_razorpay_signature_verification_round_trip():
    payload = 'order_123|pay_123'
    signature = server.generate_razorpay_signature(payload, 'test-secret')

    assert server.verify_razorpay_signature('order_123', 'pay_123', signature, 'test-secret')
    assert not server.verify_razorpay_signature('order_123', 'pay_123', 'bad-signature', 'test-secret')
