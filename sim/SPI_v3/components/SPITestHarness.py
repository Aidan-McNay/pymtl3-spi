'''
==========================================================================
SPITestHarness.py
==========================================================================
Test harness for sending messages over SPI. For use with SPIMinionAdapterComposite module

Author : Kyle Infantino and Dilan Lakhani
  Date : Jan 30, 2022
'''

from pymtl3 import *
from pymtl3.stdlib.test_utils import config_model_with_cmdline_opts

from math import ceil
import copy

#=========================================================================
# TestHarness
#=========================================================================

class SPITestHarness( object ):

  #-----------------------------------------------------------------------
  # constructor
  #-----------------------------------------------------------------------
 
  def __init__( s, DESIGN, num_components, spi_bits, cmdline_opts ):
 
    s.dut = DESIGN
    s.dut = config_model_with_cmdline_opts( s.dut, cmdline_opts, [] )
    s.dut.apply(DefaultPassGroup())

    s.dut.cs @= 1
    s.dut.sclk @= 0
    s.dut.mosi @= 0
    s.dut.miso @= 0

    s.dut.sim_reset() # Reset the simulator

    s.spi_bits = spi_bits
    s.component_bits = 0 if num_components < 2 else clog2(num_components)
    s.spi_msg_bits = s.spi_bits - s.component_bits - 2 # 2 valid bits that we do not want to account for when splitting message


  def t_mult_msg(s, req_len, resp_len, request_list, expected_resp_list, component_addr=0 ):#send messages
    """
    req/resp_len: number of bits of req/resp message
    request_list: array of messages to send to DUT
    expected_resp_list: array of expected message to receive from DUT
    components_addr: index of component messages ar ebeing sent to
    """

    req_BitsN = mk_bits(req_len)
    resp_BitsN = mk_bits(resp_len)

    if s.component_bits > 0:
      comp_addr = mk_bits(s.component_bits)(component_addr)

    #create req messages
    all_reqs = []
    for req in request_list:
      req_msgs = [] 
      i = 0
      req = req_BitsN(req)
      while i < req_len//s.spi_msg_bits: 
        req_msgs.append(req[i*s.spi_msg_bits: (i+1)*s.spi_msg_bits])
        i += 1

      if req_len % (s.spi_msg_bits) != 0: # if there are leftover bits i.e. we will have to pad with zeros to get to width of SPI channel
        req_msgs.append( zext( req[i*s.spi_msg_bits:], s.spi_msg_bits ) )

      req_msgs.reverse() # reverse because we want the most significant packet to be first in the list
      all_reqs.append(req_msgs) # append this list to the all_requests list

    all_expected_resps = []
    for resp in expected_resp_list:
      # zext to get correct length for the expected message (actual result will be a multiple of spi_msg_bits)
      exp_resp = zext(resp_BitsN(resp), s.spi_msg_bits*(ceil(resp_len/s.spi_msg_bits))) 
      all_expected_resps.append(exp_resp)

    #send req / read resp
    actual_responses = []
    resp_msgs = []

    def _assemble_msg():
      # assemble full response from spi packets
      if len(resp_msgs) == 1:
        act_resp = resp_msgs[0]
      else:
        act_resp = concat(resp_msgs[0], resp_msgs[1] )
        i = 2
        while i < len(resp_msgs):
          act_resp = concat(act_resp, resp_msgs[i])
          i+=1
      resp_msgs.clear()
      actual_responses.append(act_resp) # append assembled response to list of all responses

    def _process_resp(resp):
      if resp[s.spi_bits-1]==1:
        resp_msgs.append(resp[0:s.spi_msg_bits]) #save message if response val bit set
        if len(resp_msgs) == ceil(resp_len/s.spi_msg_bits): 
          _assemble_msg() #assemble message if enough spi response packets to make response message

    #send spi message to get status bits from MinionAdapter
    if s.component_bits > 0:
      resp_spi = s._t_spi(concat(Bits1(0), Bits1(1), comp_addr, zext(Bits1(0),s.spi_msg_bits)))
    else:
      resp_spi = s._t_spi(concat(Bits1(0), Bits1(1), zext(Bits1(0),s.spi_msg_bits)))

    _process_resp(resp_spi)
    while(resp_spi[s.spi_bits-2] == 0 ):#poll until space available. We wait for the space bit (the second most significant bit) to be 1
      if s.component_bits > 0:
        resp_spi = s._t_spi(concat(Bits1(0), Bits1(1), comp_addr, zext(Bits1(0),s.spi_msg_bits)))
      else:
        resp_spi = s._t_spi(concat(Bits1(0), Bits1(1), zext(Bits1(0),s.spi_msg_bits)))
      _process_resp(resp_spi)

    #space is now available in MinionAdapter queue for more messages
    for req in all_reqs:
      for msg in req: #sending reqs
        if s.component_bits > 0:
          resp_spi = s._t_spi(concat(Bits1(1),Bits1(1),comp_addr,msg))
        else:
          resp_spi = s._t_spi(concat(Bits1(1),Bits1(1),msg))
        _process_resp(resp_spi)

        while(resp_spi[s.spi_bits-2] == 0 ): #wait until space is available again
          if s.component_bits > 0:
            resp_spi = s._t_spi(concat(Bits1(0), Bits1(1), comp_addr, zext(Bits1(0), s.spi_msg_bits)))
          else:
            resp_spi = s._t_spi(concat(Bits1(0), Bits1(1), zext(Bits1(0), s.spi_msg_bits)))
          _process_resp(resp_spi)

    # get responses to each request
    while len(actual_responses) < len(all_expected_resps): #wait until all exepected responses received 
      if s.component_bits > 0:
        resp_spi = s._t_spi( concat(Bits1(0), Bits1(1), comp_addr, zext(Bits1(0),s.spi_msg_bits)))
      else:
        resp_spi = s._t_spi( concat(Bits1(0), Bits1(1), zext(Bits1(0),s.spi_msg_bits)))
      _process_resp(resp_spi)


    # all responses received - check results
    for i in range(len(all_expected_resps)):
      assert all_expected_resps[i] == actual_responses[i]

  #helper functions
  def _t_spi( s, pkt ): #send spi packets
    s._start_transaction()
    resp_spi = Bits1(0)
    for i in range(s.spi_bits):
      resp_bit = s._send_bit( pkt[s.spi_bits - i - 1] ) #send most significant bits first
      if i == 0:
        resp_spi = resp_bit
      else:
        resp_spi = concat( resp_spi, resp_bit )
    s._end_transaction()
    return copy.deepcopy(resp_spi)

  def _start_transaction( s ): #send bits
    # Starts a transaction by keeping cs HIGH for 3 cycles then pulling cs LOW 
    for i in range(3): # cs = 1
      # Write input values to input ports
      s.dut.sclk        @= 0
      s.dut.cs          @= 1
      s.dut.mosi        @= 1 # mosi is a dont care here bc CS is high
      s.dut.sim_eval_combinational()
      # Tick simulator one cycle
      s.dut.sim_tick()
    for i in range(3): # cs = 0, three cycles because the synchronizer takes 2 cycles for negedge to appear
      s.dut.sclk        @= 0
      s.dut.cs          @= 0
      s.dut.mosi        @= 1 # mosi is a dont care here bc CS is high
      s.dut.sim_eval_combinational()
      s.dut.sim_tick()

  def _end_transaction( s ):
    s.dut.sclk        @= 0
    s.dut.cs          @= 1
    s.dut.mosi        @= 1 # mosi is a dont care here bc CS is high
    s.dut.sim_eval_combinational()
    s.dut.sim_tick()

  def _send_bit( s, mosi): #send bits
    # This function sends bits over SPI once the transaction has been started (CS is already low)
    for i in range(3): # sclk = 0
      # Write input values to input ports
      s.dut.sclk        @= 0
      s.dut.cs          @= 0
      s.dut.mosi        @= mosi
      s.dut.sim_eval_combinational()
      # Tick simulator one cycle
      s.dut.sim_tick()

    for i in range(3): # sclk = 1
      s.dut.sclk        @= 1
      s.dut.cs          @= 0
      s.dut.mosi        @= mosi
      s.dut.sim_eval_combinational()
      s.dut.sim_tick()

    # only return MISO after 8th cycle so it has time to reflect correct value
    return copy.deepcopy(s.dut.miso) 