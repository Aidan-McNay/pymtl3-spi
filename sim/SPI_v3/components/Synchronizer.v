/*
==========================================================================
Synchronizer.v
==========================================================================
 - RTL code for the Synchronizer module.
 - It samples the input signal using the device clock and also detects
     positive and negative edges.
 - Reference: https://www.fpga4fun.com/SPI2.html
*/

module Synchronizer 
#(
    parameter reset_value = 0
)(
  input  logic clk ,
  input  logic in,
  output logic negedge_,
  output logic out,
  output logic posedge_,
  input  logic reset 
);

  logic [2:0] shreg;
  
  always_comb begin
    negedge_ = shreg[2] & ( ~shreg[1] );
    posedge_ = ( ~shreg[2] ) & shreg[1];
  end
  
  always_ff @(posedge clk) begin
    if ( reset ) begin
      shreg <= { 3{reset_value} };
    end
    else
      shreg <= { shreg[1:0], in_ };
  end

  assign out = shreg[1];

endmodule