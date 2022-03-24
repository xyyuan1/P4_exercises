#include <core.p4>
#include <v1model.p4>

const bit<16> TYPE_IPV4 = 0x0800;
const bit<16> TYPE_ARP  = 0x0806;
const bit<8>  IPPROTO_ICMP  = 0x01;
typedef bit<9>  egressSpec;

/*p4的四个组成部分: header, parser, table, controller*/

//头部由包头（Packet header）和元数据（Metadata）组成
/*ethernet头部（二层数据包头）*/
typedef bit<48> macAddr;
header Ethernet {
	macAddr  dstAddr;
	macAddr  srcAddr;
	bit<16>  etherType;
}

/*ipv4头部*/
typedef bit<32> ipv4Addr;
header Ipv4 {
    bit<4>    version;
    bit<4>    ihl;
    bit<8>    diffserv;
    bit<16>   totalLen;
    bit<16>   identification;
    bit<3>    flags;
    bit<13>   fragOffset;
    bit<8>    ttl;
    bit<8>    protocol;
    bit<16>   hdrChecksum;
    ipv4Addr  srcAddr;
    ipv4Addr  dstAddr;
}

/*元数据（设置为空）*/
struct metadata {
    //empty
}

/*headers头部组成*/
struct headers {
    Ethernet   ethernet;
    Ipv4       ipv4;
}

/*Parser
  一个开始状态和两个最终状态的状态机
  一个Parser对应多个状态
*/
/*Parser输入*/
parser MyParser (packet_in packet, out headers hdr, inout metadata meta, inout standard_metadata_t standard_metadata) {
	/*transition：在不同的state之间切换
      extract：   将目前的packet以特定的header取出来，取出来的各部分长度以header定义的为主。
     */
    /*开始状态*/
    state start {
        transition parse_ethernet; //开始先转至parse_ethernet状态
    }

    state parse_ethernet {
        packet.extract(hdr.ethernet); //提取数据包头
        transition select(hdr.ethernet.etherType) {
            TYPE_IPV4: parse_ipv4;    
            default: accept;
        }
    }

    state parse_ipv4 {
        packet.extract(hdr.ipv4);   //将包以ipv4包头取出
        transition accept;        //根据etherType转移状态，直到accept结束
    }

}

//校验和检验

control MyVerifyChecksum(inout headers hdr, inout metadata meta) {   
    apply {  } //不执行动作
}


//Ingress Processing 数据包处理

control MyIngress(inout headers hdr, inout metadata meta, inout standard_metadata_t standard_metadata) {
    /*丢包动作定义*/
    action drop() {  
        mark_to_drop(standard_metadata);
    }
    /*三层转发动作定义*/
    action ipv4_forward(macAddr dstAddr, egressSpec port) {
        standard_metadata.egress_spec = port;
        hdr.ethernet.srcAddr = hdr.ethernet.dstAddr;
        hdr.ethernet.dstAddr = dstAddr;
        hdr.ipv4.ttl = hdr.ipv4.ttl - 1;    //生存时间减一
    }
    
    /*table定义*/
    table ipv4_lpm {
        key = {
            hdr.ipv4.dstAddr: lpm;  //数据包头部中的ipv4头部的目标地址
        }
        actions = {
            ipv4_forward;//转发
            drop;        //丢包
            NoAction;
        }
        size = 1024;
        default_action = drop();
    }
    
    //数据处理部分：lpm匹配
    apply {
        if (hdr.ipv4.isValid()) {
            ipv4_lpm.apply();   
        }
    }
}

/*Egress processing*/
control MyEgress(inout headers hdr, inout metadata meta, inout standard_metadata_t standard_metadata) {
    apply {  }   //不执行动作，可删去
}

//校验和计算
control MyComputeChecksum(inout headers hdr, inout metadata meta) {
    apply {
        //更新校验和
        update_checksum (
            hdr.ipv4.isValid(),
            { 
                hdr.ipv4.version,
                hdr.ipv4.ihl,
                hdr.ipv4.diffserv,
                hdr.ipv4.totalLen,
                hdr.ipv4.identification,
                hdr.ipv4.flags,
                hdr.ipv4.fragOffset,
                hdr.ipv4.ttl,
                hdr.ipv4.protocol,
                hdr.ipv4.srcAddr,
                hdr.ipv4.dstAddr 
            },
            hdr.ipv4.hdrChecksum,
            HashAlgorithm.csum16
        );
    }
}

//Deparser
/*数据包重组*/
control MyDeparser(packet_out packet, in headers hdr) {
    apply {
        packet.emit(hdr.ethernet);
        packet.emit(hdr.ipv4);
    }
}

//Switch

V1Switch(
    MyParser(),
    MyVerifyChecksum(),
    MyIngress(),
    MyEgress(),
    MyComputeChecksum(),
    MyDeparser()
) main; //主函数
