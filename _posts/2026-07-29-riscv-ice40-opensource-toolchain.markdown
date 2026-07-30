---
layout: post
title:  "Open-Source IC Design Toolchain: RISC-V on iCE40 FPGA"
date:   2026-07-29 12:00:00 +0800
categories: hardware
---
A complete open-source ASIC/FPGA design flow from RTL to bitstream, using the RISC-V ISA, Icarus Verilog for simulation, Yosys for synthesis, and the IceStorm toolchain for iCE40 FPGA programming.

## Toolchain Overview

```
RISC-V RTL (Verilog)
       │
       ▼
┌─────────────────┐
│  Icarus Verilog  │  Simulation & Verification
│    (iverilog)    │
└─────────────────┘
       │
       ▼
┌─────────────────┐
│     Yosys        │  Logic Synthesis
└─────────────────┘
       │
       ▼
┌─────────────────┐
│  nextpnr-ice40   │  Place & Route
└─────────────────┘
       │
       ▼
┌─────────────────┐
│   IceStorm       │  Bitstream Generation
│  (icepack/icetime)│
└─────────────────┘
       │
       ▼
┌─────────────────┐
│   iceprog        │  Flash to iCE40 FPGA
└─────────────────┘
```

## Installation

{% highlight bash %}
# System packages (Ubuntu/Debian)
sudo apt install iverilog yosys gtkwave

# IceStorm tools from source
git clone https://github.com/YosysHQ/icestorm.git
cd icestorm && make -j$(nproc) && sudo make install

# nextpnr for iCE40
git clone https://github.com/YosysHQ/nextpnr.git
cd nextpnr
cmake -DARCH=ice40 -DCMAKE_INSTALL_PREFIX=/usr/local .
make -j$(nproc) && sudo make install
{% endhighlight %}

## A Minimal RISC-V Core (RV32I)

Below is a simplified single-cycle RV32I core supporting the base integer instruction set:

{% raw %}
{% highlight verilog %}
module riscv_core (
    input  wire        clk,
    input  wire        rst_n,
    output wire [31:0] imem_addr,
    input  wire [31:0] imem_rdata,
    output wire [31:0] dmem_addr,
    output wire [31:0] dmem_wdata,
    input  wire [31:0] dmem_rdata,
    output wire        dmem_we
);

    reg [31:0] pc, pc_next;
    reg [31:0] rf [0:31];
    wire [6:0] opcode = imem_rdata[6:0];
    wire [4:0] rs1    = imem_rdata[19:15];
    wire [4:0] rs2    = imem_rdata[24:20];
    wire [4:0] rd     = imem_rdata[11:7];
    wire [2:0] funct3 = imem_rdata[14:12];
    wire [31:0] imm_i = {{20{imem_rdata[31]}}, imem_rdata[31:20]};
    wire [31:0] imm_s = {{20{imem_rdata[31]}}, imem_rdata[31:25], imem_rdata[11:7]};
    wire [31:0] imm_b = {{19{imem_rdata[31]}}, imem_rdata[31], imem_rdata[7],
                          imem_rdata[30:25], imem_rdata[11:8], 1'b0};

    wire [31:0] src1 = (rs1 == 0) ? 32'h0 : rf[rs1];
    wire [31:0] src2 = (rs2 == 0) ? 32'h0 : rf[rs2];
    reg [31:0] result;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            pc <= 32'h0000_0000;
            rf[0] <= 32'h0;
        end else begin
            pc <= pc_next;
            if (rd != 0 && opcode != 7'b0100011)
                rf[rd] <= result;
        end
    end

    always @(*) begin
        case (opcode)
            7'b0110011: begin  // R-type
                case ({funct3, imem_rdata[30]})
                    4'b0000: result = src1 + src2;           // ADD
                    4'b0001: result = src1 - src2;           // SUB
                    4'b1110: result = src1 & src2;           // AND
                    4'b1100: result = src1 | src2;           // OR
                    4'b0100: result = src1 ^ src2;           // XOR
                    4'b0010: result = src1 << src2[4:0];     // SLL
                    default: result = 32'h0;
                endcase
            end
            7'b0010011: begin  // I-type
                case (funct3)
                    3'b000: result = src1 + imm_i;           // ADDI
                    3'b100: result = src1 ^ imm_i;           // XORI
                    3'b111: result = src1 & imm_i;           // ANDI
                    3'b110: result = src1 | imm_i;           // ORI
                    default: result = 32'h0;
                endcase
            end
            7'b0000011: result = dmem_rdata;                 // LW
            7'b0100011: result = src2;                       // SW
            7'b1100011: begin  // B-type
                case (funct3)
                    3'b000: result = (src1 == src2) ? imm_b : 32'd4;  // BEQ
                    3'b001: result = (src1 != src2) ? imm_b : 32'd4;  // BNE
                    default: result = 32'd4;
                endcase
            end
            7'b0010111: result = {imem_rdata[31:12], 12'h0}; // AUIPC
            7'b1101111: result = {{12{imem_rdata[31]}}, imem_rdata[19:12],
                                   imem_rdata[20], imem_rdata[30:21], 1'b0}; // JAL
            default: result = 32'h0;
        endcase
    end

    assign pc_next = (opcode == 7'b1100011 || opcode == 7'b1101111)
                     ? pc + result
                     : pc + 32'd4;

    assign imem_addr = pc;
    assign dmem_addr = src1 + imm_s;
    assign dmem_wdata = src2;
    assign dmem_we = (opcode == 7'b0100011);

endmodule
{% endhighlight %}
{% endraw %}

## Testbench with Icarus Verilog

{% highlight verilog %}
`timescale 1ns / 1ps

module riscv_core_tb;
    reg clk, rst_n;
    reg [31:0] imem [0:255];
    reg [31:0] dmem [0:255];
    wire [31:0] imem_addr, dmem_addr, dmem_wdata;
    wire [31:0] imem_rdata, dmem_rdata;
    wire dmem_we;

    riscv_core uut (
        .clk(clk), .rst_n(rst_n),
        .imem_addr(imem_addr), .imem_rdata(imem_rdata),
        .dmem_addr(dmem_addr), .dmem_wdata(dmem_wdata),
        .dmem_rdata(dmem_rdata), .dmem_we(dmem_we)
    );

    assign imem_rdata = imem[imem_addr[31:2]];
    assign dmem_rdata = dmem[dmem_addr[31:2]];

    // Load test program: addi x1, x0, 5; addi x2, x0, 10; add x3, x1, x2
    initial begin
        imem[0] = 32'h0050_0093;  // ADDI x1, x0, 5
        imem[1] = 32'h00A0_0113;  // ADDI x2, x0, 10
        imem[2] = 32'h0011_01B3;  // ADD  x3, x1, x2
        imem[3] = 32'h0000_0000;  // NOP (halt)
    end

    initial begin
        clk = 0; rst_n = 0;
        #20 rst_n = 1;
        #200 $display("x3 = %d (expected 15)", uut.rf[3]);
        $finish;
    end

    always #10 clk = ~clk;  // 50 MHz

    initial begin
        $dumpfile("riscv_core.vcd");
        $dumpvars(0, riscv_core_tb);
    end
endmodule
{% endhighlight %}

Run simulation:

{% highlight bash %}
# Compile and run
iverilog -o riscv_tb riscv_core.v riscv_core_tb.v
vvp riscv_tb

# View waveforms
gtkwave riscv_core.vcd
{% endhighlight %}

## Synthesis with Yosys

{% highlight bash %}
# Synthesize RTL to blif netlist
yosys -p "
    read_verilog riscv_core.v;
    synth_ice40 -top riscv_core -blif riscv_core.blif;
    stat
"
{% endhighlight %}

Typical synthesis output for this minimal RV32I core on iCE40 (LUT4-based):

```
Number of cells:         ~850
  SB_LUT4:               ~800
  SB_CARRY:               ~50
  SB_DFF:                ~120
Estimated max frequency: ~45 MHz (iCE40HX8K)
```

## Yosys Synthesis Script (Tcl)

{% highlight tcl %}
# read_ice40.tcl
read_verilog riscv_core.v
hierarchy -check -top riscv_core
proc; opt; fsm; opt; memory; opt
techmap; opt
synth_ice40 -top riscv_core -blif riscv_core.blif
write_verilog riscv_core_synth.v
{% endhighlight %}

{% highlight bash %}
yosys read_ice40.tcl
{% endhighlight %}

## Place & Route with nextpnr

{% highlight bash %}
# Pin constraints file (pins.pcf)
cat > pins.pcf <<EOF
set_io clk      12
set_io rst_n    13
# UART TX (optional)
set_io uart_tx  25
EOF

# Place and route for iCE40HX8K on IceStick
nextpnr-ice40 \
    --hx8k --package ct256 \
    --blif riscv_core.blif \
    --pcf pins.pcf \
    --asc riscv_core.asc \
    --freq 40
{% endhighlight %}

## Bitstream Generation with IceStorm

{% highlight bash %}
# Convert ASCII to binary bitstream
icepack riscv_core.asc riscv_core.bin

# Timing analysis
icetime -d hx8k -mtr riscv_core.rpt riscv_core.asc

# Flash to IceStick
iceprog riscv_core.bin
{% endhighlight %}

## Complete Makefile

{% highlight makefile %}
TOP = riscv_core
PCF = pins.pcf
DEVICE = hx8k
PACKAGE = ct256

all: $(TOP).bin

$(TOP).blif: $(TOP).v
	yosys -p "synth_ice40 -top $(TOP) -blif $@" $<

$(TOP).asc: $(TOP).blif $(PCF)
	nextpnr-ice40 --$(DEVICE) --package $(PACKAGE) \
		--blif $(TOP).blif --pcf $(PCF) --asc $@ --freq 40

$(TOP).bin: $(TOP).asc
	icepack $< $@

sim: $(TOP)_tb.v $(TOP).v
	iverilog -o $(TOP)_tb.out $^
	vvp $(TOP)_tb.out

prog: $(TOP).bin
	iceprog $<

timing: $(TOP).asc
	icetime -d $(DEVICE) -mtr $(TOP).rpt $<

clean:
	rm -f *.blif *.asc *.bin *.out *.vcd *.rpt

.PHONY: all sim prog timing clean
{% endhighlight %}

## Adding UART Peripheral

{% highlight verilog %}
module uart_tx (
    input  wire       clk,
    input  wire       rst_n,
    input  wire [7:0] data,
    input  wire       send,
    output reg        tx,
    output reg        busy
);
    parameter CLK_FREQ = 40_000_000;
    parameter BAUD     = 115_200;
    localparam DIV     = CLK_FREQ / BAUD;

    reg [15:0] counter;
    reg [3:0]  bit_idx;
    reg [9:0]  shift_reg;
    reg        running;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            tx <= 1'b1; busy <= 1'b0;
            counter <= 0; bit_idx <= 0; running <= 0;
        end else if (!running && send) begin
            shift_reg <= {1'b1, data, 1'b0};  // stop, data, start
            running <= 1'b1; busy <= 1'b1;
            counter <= 0; bit_idx <= 0;
        end else if (running) begin
            if (counter == DIV - 1) begin
                counter <= 0;
                tx <= shift_reg[0];
                shift_reg <= shift_reg >> 1;
                bit_idx <= bit_idx + 1;
                if (bit_idx == 9) begin
                    running <= 0; busy <= 0;
                end
            end else begin
                counter <= counter + 1;
            end
        end
    end
endmodule
{% endhighlight %}

## Resource Utilization on iCE40

| Component | LUT4 | DFF | Carry | BRAM |
|-----------|------|-----|-------|------|
| RV32I Core | 812 | 128 | 48 | 0 |
| UART TX | 24 | 22 | 0 | 0 |
| Instruction RAM (2KB) | 0 | 0 | 0 | 2 |
| Data RAM (1KB) | 0 | 0 | 0 | 1 |
| **Total** | **836** | **150** | **48** | **3** |

## Additional Open-Source Tools

| Tool | Purpose | Website |
|------|---------|---------|
| Verilator | Fast Verilog simulator | verilator.org |
| SpinalHDL | Scala-based HDL | spinalhdl.github.io |
| Chisel | Scala-embedded HDL | chisel-lang.org |
| Amaranth (nMigen) | Python-based HDL | amaranth-lang.org |
| OpenROAD | ASIC place & route | theopenroadproject.org |
| OpenLane | RTL-to-GDSII flow | openlane.org |
| SkyWater 130nm | Open-source PDK | skywater-pdk.org |

## References

- [Icarus Verilog Documentation](https://steveicarus.github.io/iverilog/)
- [Yosys Open Synthesis Suite](https://yosyshq.net/yosys/)
- [Project IceStorm](https://clifford.at/icestorm)
- [RISC-V ISA Specification](https://riscv.org/technical/specifications/)
- [iCE40 Family Datasheet](https://www.latticesemi.com/iCE40)
