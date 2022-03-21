'''
==========================================================================
SPIMinionAdapterCompositePRTL.py
==========================================================================
A composition module combining the SPIMinion and SPIMinionAdapter 

Author : Kyle Infantino
  Date : Dec 7, 2021

'''

from pymtl3 import *
from .SPIMinionPRTL import SPIMinionPRTL
from .SPIMinionAdapterPRTL import SPIMinionAdapterPRTL
from pymtl3.stdlib.stream.ifcs import RecvIfcRTL, SendIfcRTL

class SPIMinionAdapterCompositePRTL( Component ):

  def construct( s, nbits=34, num_entries=1 ):
    s.nbits = nbits

    s.cs   = InPort ()
    s.sclk = InPort ()
    s.mosi = InPort ()
    s.miso = OutPort()

    s.recv = RecvIfcRTL( mk_bits(nbits-2))
    s.send = SendIfcRTL( mk_bits(nbits-2))

    s.minion = m = SPIMinionPRTL(nbits)
    m.cs //= s.cs
    m.sclk //= s.sclk
    m.mosi //= s.mosi
    m.miso //= s.miso

    s.adapter = a = SPIMinionAdapterPRTL(nbits,num_entries)
    a.pull.en //= m.pull.en
    a.pull.msg.val //= m.pull.msg[nbits-1]
    a.pull.msg.spc //= m.pull.msg[nbits-2]
    a.pull.msg.data //= m.pull.msg[0:nbits-2]
    a.push.en //= m.push.en
    a.push.msg.val_wrt //= m.push.msg[nbits-1]
    a.push.msg.val_rd //= m.push.msg[nbits-2]
    a.push.msg.data //= m.push.msg[0:nbits-2]

    a.send //= s.send
    a.recv //= s.recv
  
  def line_trace( s ):
    return f"push_en {s.adapter.push.en} push_msg {s.adapter.push.msg.val_wrt} {s.adapter.push.msg.val_rd} {s.adapter.push.msg.data} pull_en {s.adapter.pull.en} pull_msg {s.adapter.pull.msg.val} {s.adapter.pull.msg.spc} {s.adapter.pull.msg.data}"