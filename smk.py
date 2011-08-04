import socket
import seto_pb2
import struct
from Queue import Queue
from threading import Thread

class Client(Thread):

    class Out(Thread):
        def __init__(self, sock, seq=1):
            self.sock = sock
            self.seq = seq
            self.q = Queue(0)
            Thread.__init__(self)
        
        def send(self, msg):
            self.q.put(msg)
            # todo: for persistence this should also log to a file
            # that means we need 2 threads here, one for allocating
            # sequence numbers and logging to file, the other as the
            # sender thread

        def run(self):
            while True:
                msg = None
                msg_bytes = None
                byte_count = None
                header = None

                msg = self.q.get(True)
                msg.seq = self.seq
                msg_bytes = msg.SerializeToString()
                byte_count = len(msg_bytes)
                # 0:1 Bytes:15 Data:(Bytes*8)
                header = struct.pack('>H', byte_count)
                # header already has 0 as first bit if byte_count < what 15 bits can store
                # a 1 would mean it's a non-sequenced message
                self.sock.send(header + msg_bytes)
                self.q.task_done()
                self.seq += 1

    def __init__(self):
        Thread.__init__(self)

    def order(self, qty, price, side, group, contract):
        msg = seto_pb2.seq_message()
        msg.payload.order_create.quantity = qty
        msg.payload.order_create.price = price
        msg.payload.order_create.side = side
        msg.payload.order_create.group = group
        msg.payload.order_create.contract = contract
        self.out.send(msg)

    def order_cancel(self, order):
        msg = seto_pb2.seq_message()
        msg.payload.order_cancel.order = order
        self.out.send(msg)

    def ping(self):
        msg = seto_pb2.seq_message()
        msg.payload.ping = True
        self.out.send(msg)

    def subscribe(self, group):
        msg = seto_pb2.seq_message()
        msg.payload.market_subscription.group = group
        self.out.send(msg)

    def unsubscribe(self, group):
        msg = seto_pb2.seq_message()
        msg.payload.market_unsubscription.group = group
        self.out.send(msg)

    def login(self, host, port, username, password, session=None, inseq=1, outseq=1):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        self.out = Client.Out(sock, outseq)
        self.out.start()
        self.inseq = inseq
        msg = seto_pb2.seq_message()
        msg.payload.login.username = username
        msg.payload.login.password = password
        if session:
            msg.payload.login.session = session
        self.out.send(msg)
        self.sock = sock
        self.start()

    def run(self):
        while True:
            header_bytes = self.sock.recv(2)
            (header,) = struct.unpack('>H', header_bytes)
            if header&32768:
                byte_count = header - 32768
                msg_bytes = self.sock.recv(byte_count)
                msg = seto_pb2.transient()
                msg.ParseFromString(msg_bytes)
                self.handle_transient(msg)
            else:
                msg_bytes = self.sock.recv(header)
                msg = seto_pb2.seq_message()
                msg.ParseFromString(msg_bytes)
                if self.pre_handle(msg):
                    try:
                        self.handle(msg)
                        self.inseq += 1
                    except Exception, e:
                        print "Error handling message", msg, e

    def pre_handle(self, msg):
        if msg.seq == self.inseq:
            return True # correct sequence
        elif msg.payload.replay.seq:
            # replay message, sequence not important, process it here
            return False
        elif msg.seq > self.inseq:
            replay = seto_pb2.seq_message()
            replay.payload.replay.seq = self.inseq
            self.out.send(replay)
            return False
        else:
            return False

    def handle(self, msg):
        if msg.payload.login_response.session:
            self.session = msg.payload.login_response.session
            self.out.seq = msg.payload.login_response.reset
            print "Session", msg.payload.login_response.session
        elif msg.payload.order_accepted.order:
            print "Order Accepted", msg.payload.order_accepted.seq, msg.payload.order_accepted.order
        elif msg.payload.order_executed.order:
            print "Order Executed", msg.payload.order_executed.order, \
                    msg.payload.order_executed.price,\
                    msg.payload.order_executed.quantity
        elif msg.payload.order_cancelled.order:
            print "Order Cancelled", msg.payload.order_cancelled.order, msg.payload.order_cancelled.reason
        elif msg.payload.pong:
            print "Pong"
        elif msg.payload.market_subscribed.group:
            print "Subscribed to market", msg.payload.market_subscribed.group

    def handle_transient(self, msg):
        if msg.push_accepted.quantity:
            payload = msg.push_accepted
            print "Push Accepted", payload.quantity, payload.price, payload.side
        elif msg.push_executed.quantity:
            payload = msg.push_executed
            print "Push Execution", payload.quantity, payload.price, payload.side
