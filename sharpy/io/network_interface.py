import socket
import selectors
import logging
import sharpy.io.message_interface as message_interface
import sharpy.io.inout_variables as inout_variables
import sharpy.utils.settings as settings

sel = selectors.DefaultSelector()

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=20)
logger = logging.getLogger(__name__)


class NetworkLoader:
    """
    Settings for each input or output port

    See Also:
        Endianness: https://docs.python.org/3/library/struct.html#byte-order-size-and-alignment
    """
    settings_types = dict()
    settings_default = dict()
    settings_description = dict()
    settings_options = dict()

    settings_types['variables_filename'] = 'str'
    settings_default['variables_filename'] = None
    settings_description['variables_filename'] = 'Path to YAML file containing input/output variables'

    settings_types['byte_ordering'] = 'str'
    settings_default['byte_ordering'] = 'little'
    settings_description['byte_ordering'] = 'Desired endianness byte ordering'
    settings_options['byte_ordering'] = ['little', 'big']

    settings_types['input_network_settings'] = 'dict'
    settings_default['input_network_settings'] = dict()
    settings_description['input_network_settings'] = 'Settings for the input network.'

    settings_types['output_network_settings'] = 'dict'
    settings_default['output_network_settings'] = dict()
    settings_description['output_network_settings'] = 'Settings for the output network.'

    settings_table = settings.SettingsTable()
    __doc__ += settings_table.generate(settings_types, settings_default, settings_description)

    def __init__(self):
        self.settings = None

        self.byte_ordering = '<'

    def initialise(self, in_settings):
        self.settings = in_settings
        settings.to_custom_types(self.settings, self.settings_types, self.settings_default,
                                 no_ctype=True, options=self.settings_options)

        if self.settings['byte_ordering'] == 'little':
            self.byte_ordering = '<'
        elif self.settings['byte_ordering'] == 'big':
            self.byte_ordering = '>'
        else:
            raise KeyError('Unknown byte ordering {}'.format(self.settings['byte_ordering']))

    def get_inout_variables(self):
        set_of_variables = inout_variables.SetOfVariables()
        set_of_variables.load_variables_from_yaml(self.settings['variables_filename'])
        set_of_variables.set_byte_ordering(self.byte_ordering)

        return set_of_variables

    def get_networks(self):

        out_network = OutNetwork()
        out_network.initialise('rw', in_settings=self.settings['output_network_settings'])
        out_network.set_byte_ordering(self.byte_ordering)
        # TODO: check initialisation mode of output network

        in_network = InNetwork()
        in_network.initialise('r', in_settings=self.settings['input_network_settings'])
        in_network.set_byte_ordering(self.byte_ordering)
        return out_network, in_network


class Network:

    settings_types = dict()
    settings_default = dict()
    settings_description = dict()

    settings_types['address'] = 'str'
    settings_default['address'] = '127.0.0.1'
    settings_description['address'] = 'Own network address.'

    settings_types['port'] = 'int'
    settings_default['port'] = 65000
    settings_description['port'] = 'Own port.'

    def __init__(self, host=None, port=None):  # remove args when this is tested

        self.addr = (host, port)  # own address

        self.sock = None
        self.sel = sel

        self.clients = list()

        self.queue = None  # queue object

        self.settings = None

        self._byte_ordering = '<'

    def set_byte_ordering(self, value):
        self._byte_ordering = value

    def _set_selector_events_mask(self, mode):
        """Set selector to listen for events: mode is 'r', 'w', or 'rw'."""
        events = get_events(mode)
        logger.info('Modifying selector to {}'.format(mode))
        sel.modify(self.sock, events, data=self)

    def initialise(self, mode, in_settings):
        self.settings = in_settings
        settings.to_custom_types(self.settings, self.settings_types, self.settings_default,
                                 no_ctype=True)
        self.addr = (self.settings['address'], self.settings['port'])

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(self.addr)
        logger.info('Binded socket to {}'.format(self.addr))
        events = get_events(mode)
        logger.info('Host: {}'.format(socket.gethostname()))
        self.sock.setblocking(False)
        sel.register(self.sock, events, data=self)

    def send(self, msg, dest_addr):
        if type(dest_addr) is list:
            for dest in dest_addr:
                self._sendto(msg, dest)
        elif type(dest_addr) is tuple:
            self._sendto(msg, dest_addr)

    def set_queue(self, queue):
        self.queue = queue

    def _sendto(self, msg, address):
        logger.info('Network - Sending')
        self.sock.sendto(msg, address)
        logger.info('Network - Sent data packet to {}'.format(address))

    def receive(self, msg_length=1024):
        r_msg, client_addr = self.sock.recvfrom(msg_length)  # adapt message length
        logger.info('Received a {}-byte long data packet from {}'.format(len(r_msg), client_addr))
        self.add_client(client_addr)
        # r_msg = struct.unpack('f', r_msg)  # need to move decoding to dedicated message processing
        return r_msg
        # return recv_data

    def process_events(self, mask):  # should only have the relevant queue
        logger.info('should not be here')
        pass
        # if mask and selectors.EVENT_READ:
        #     logger.info('Network - Receiving')
        #     msg = self.receive()
        #     # would need to process msg beforehand
        #     in_queue.put(msg)
        #     logger.info('Network - Placed message in the queue')
        #
        # if mask and selectors.EVENT_WRITE:
        #     msg = out_queue.get()
        #     logger.info('Network - Got message from the queue')
        #     self.send(msg, self.clients)

        # return in_queue, out_queue: not needed, processing done on original objects

    def add_client(self, client_addr):
        if type(client_addr) is tuple:
            self._add_client(client_addr)
        elif type(client_addr) is list:
            for client in client_addr:
                self._add_client(client)

    def _add_client(self, client_addr):
        if client_addr not in self.clients:
            self.clients.append(client_addr)
            logger.info('Added new client to list {}'.format(client_addr))

    def close(self):
        self.sel.unregister(self.sock)
        logger.info('Unregistered socket from selectors')
        self.sock.close()
        logger.info('Closed socket')


class OutNetwork(Network):

    settings_types = Network.settings_types.copy()
    settings_default = Network.settings_default.copy()
    settings_description = Network.settings_description.copy()

    settings_types['port'] = 'int'
    settings_default['port'] = 65000
    settings_description['port'] = 'Own port for output network'

    settings_types['send_on_demand'] = 'bool'
    settings_default['send_on_demand'] = True
    settings_description['send_on_demand'] = 'Waits for a signal demanding the output data. Else, sends to destination' \
                                             ' buffer'

    settings_types['destination_address'] = 'list(str)'
    settings_default['destination_address'] = list()  # add check to raise error if send_on_demand false and this is empty
    settings_description['destination_address'] = 'List of addresses to send output data. If ``send_on_demand`` is ' \
                                                  '``False`` this is a required setting.'

    settings_types['destination_ports'] = 'list(int)'
    settings_default['destination_ports'] = list()
    settings_description['destination_ports'] = 'List of ports number for the destination addresses.'

    def initialise(self, mode, in_settings):
        super().initialise(mode, in_settings)

        if self.settings['send_on_demand'] is False and len(self.settings['destination_address']) == 0:
            logger.warning('No destination host address provided')

        clients = list(zip(self.settings['destination_address'], self.settings['destination_ports']))
        self.add_client(clients)

    def process_events(self, mask):
        # if not self.queue.empty():
        #     self._set_selector_events_mask('rw')

        if mask and selectors.EVENT_READ:
            if self.settings['send_on_demand']:
                logger.info('Out Network - waiting for request for data')
                msg = self.receive()
                # get variable that has been demanded, this would be easy if a SetOfVariables was sent in the queue
                # logger.info('Received request for data {}'.format(msg))
                logger.info('Received request for data')
        if mask and selectors.EVENT_WRITE and not self.queue.empty():
            # if mask and selectors.EVENT_WRITE:
        # if not self.queue.empty:
            logger.info('Out Network ready to receive from the queue')
            # value = self.queue.get()  # check that it waits for the queue not to be empty
            set_of_vars = self.queue.get()  # always gets latest time step info
            logger.info('Out Network - got message from queue')
            # for out_idx in set_of_vars.out_variables:
            #     value = set_of_vars[out_idx].value
            value = set_of_vars.encode()
            logger.info('Message of length {} bytes ready to send'.format(len(value)))
            self.send(value, self.clients)
                # self.send(value, self.clients)


class InNetwork(Network):

    settings_types = Network.settings_types.copy()
    settings_default = Network.settings_default.copy()
    settings_description = Network.settings_description.copy()

    settings_types['port'] = 'int'
    settings_default['port'] = 65001
    settings_description['port'] = 'Own port for input network'

    def __init__(self):
        super().__init__()
        self._in_message_length = 1024
        self._recv_buffer = b''

    def set_message_length(self, value):
        self._in_message_length = value
        logger.info('Set input message size to {} bytes'.format(self._in_message_length))

    def process_events(self, mask):
        self.sock.setblocking(False)
        if mask and selectors.EVENT_READ:
            logger.info('In Network - waiting for input data of size {}'.format(self._in_message_length))
            msg = self.receive(self._in_message_length)
            self._recv_buffer += msg
            # any required processing
            # send list of tuples
            if len(self._recv_buffer) == self._in_message_length:
                logger.info('In Network - enough bytes read')
                list_of_variables = message_interface.decoder(self._recv_buffer, byte_ordering=self._byte_ordering)
                self.queue.put(list_of_variables)
                logger.info('In Network - put data in the queue')
                self._recv_buffer = b''  # clean up


def get_events(mode):
    if mode == "r":
        events = selectors.EVENT_READ
    elif mode == "w":
        events = selectors.EVENT_WRITE
    elif mode == "rw":
        events = selectors.EVENT_READ | selectors.EVENT_WRITE
    else:
        raise ValueError(f"Invalid events mask mode {repr(mode)}.")

    return events
