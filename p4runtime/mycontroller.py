#!/usr/bin/env python3
import argparse
import grpc
import os
import sys
from time import sleep

# 引入库和需要用到的 p4runtime_lib
sys.path.append(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 '../../utils/'))
import p4runtime_lib.bmv2
from p4runtime_lib.switch import ShutdownAllSwitchConnections
import p4runtime_lib.helper

def writeTunnelRules(p4info_helper, ingress_sw, egress_sw, tunnel_id,
                     dst_eth_addr, dst_ip_addr,SWITCH_TO_HOST_PORT,SWITCH_TO_SWITCH_PORT):
    # 1) Tunnel Ingress Rule
    # 将数据封装到指定ID的隧道上
    table_entry = p4info_helper.buildTableEntry(
        table_name="MyIngress.ipv4_lpm",
        match_fields={
            "hdr.ipv4.dstAddr": (dst_ip_addr, 32)
        },
        action_name="MyIngress.myTunnel_ingress",
        action_params={
            "dst_id": tunnel_id,
        })
    ingress_sw.WriteTableEntry(table_entry)
    print("Installed ingress tunnel rule on %s" % ingress_sw.name)

    # 2) Tunnel Transit Rule
    # 指定数据从交换机输出的端口，基于指定的隧道ID转发数据。
    table_entry = p4info_helper.buildTableEntry(
        table_name="MyIngress.myTunnel_exact",
        match_fields={
            "hdr.myTunnel.dst_id": tunnel_id
        },
        action_name="MyIngress.myTunnel_forward",
        action_params={
            "port": SWITCH_TO_SWITCH_PORT
        })
    ingress_sw.WriteTableEntry(table_entry)
    print("Installed transit tunnel rule on %s" % ingress_sw.name)

    # 3) Tunnel Egress Rule
    # 指定主机连接交换机的端口，使用特定的隧道ID对数据解封装，并且发送数据到主机。
    table_entry = p4info_helper.buildTableEntry(
        table_name="MyIngress.myTunnel_exact",
        match_fields={
            "hdr.myTunnel.dst_id": tunnel_id
        },
        action_name="MyIngress.myTunnel_egress",
        action_params={
            "dstAddr": dst_eth_addr,
            "port": SWITCH_TO_HOST_PORT
        })
    egress_sw.WriteTableEntry(table_entry)
    print("Installed egress tunnel rule on %s" % egress_sw.name)


def readTableRules(p4info_helper, sw):

    print('\n----- Reading tables rules for %s -----' % sw.name)
    for response in sw.ReadTableEntries():
        for entity in response.entities:
            entry = entity.table_entry
            table_name = p4info_helper.get_tables_name(entry.table_id)
            print('%s: ' % table_name, end=' ')
            for m in entry.match:
                print(p4info_helper.get_match_field_name(table_name, m.field_id), end=' ')
                print('%r' % (p4info_helper.get_match_field_value(m),), end=' ')
            action = entry.action.action
            action_name = p4info_helper.get_actions_name(action.action_id)
            print('->', action_name, end=' ')
            for p in action.params:
                print(p4info_helper.get_action_param_name(action_name, p.param_id), end=' ')
                print('%r' % p.value, end=' ')
            print()

def printCounter(p4info_helper, sw, counter_name, index):
    #对传输的数据包进行监听并读取、打印
    for response in sw.ReadCounters(p4info_helper.get_counters_id(counter_name), index):
        for entity in response.entities:
            counter = entity.counter_entry
            print("%s %s %d: %d packets (%d bytes)" % (
                sw.name, counter_name, index,
                counter.data.packet_count, counter.data.byte_count
            ))

def printGrpcError(e):
    print("gRPC Error:", e.details(), end=' ')
    status_code = e.code()
    print("(%s)" % status_code.name, end=' ')
    traceback = sys.exc_info()[2]
    print("[%s:%d]" % (traceback.tb_frame.f_code.co_filename, traceback.tb_lineno))

def main(p4info_file_path, bmv2_file_path):
    p4info_helper = p4runtime_lib.helper.P4InfoHelper(p4info_file_path)

    try:
        #创建三个交换机的grpc连接
        s1 = p4runtime_lib.bmv2.Bmv2SwitchConnection(
            name='s1',
            address='127.0.0.1:50051',
            device_id=0,
            proto_dump_file='logs/s1-p4runtime-requests.txt')
        s2 = p4runtime_lib.bmv2.Bmv2SwitchConnection(
            name='s2',
            address='127.0.0.1:50052',
            device_id=1,
            proto_dump_file='logs/s2-p4runtime-requests.txt')
        s3 = p4runtime_lib.bmv2.Bmv2SwitchConnection(
            name='s3',
            address='127.0.0.1:50053',
            device_id=2,
            proto_dump_file='logs/s3-p4runtime-requests.txt')

        # Send master arbitration update message to establish this controller as
        # master (required by P4Runtime before performing any other write operation)
        s1.MasterArbitrationUpdate()
        s2.MasterArbitrationUpdate()
        s3.MasterArbitrationUpdate()


        # 将p4程序安装到交换机中
        s1.SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                       bmv2_json_file_path=bmv2_file_path)
        print("Installed P4 Program using SetForwardingPipelineConfig on s1")
        s2.SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                       bmv2_json_file_path=bmv2_file_path)
        print("Installed P4 Program using SetForwardingPipelineConfig on s2")
        s3.SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                       bmv2_json_file_path=bmv2_file_path)
        print("Installed P4 Program using SetForwardingPipelineConfig on s3")

        # 根据拓扑结构定义三个交换机与主机连接的端口，以及交换机与交换机之间的端口规则
        writeTunnelRules(p4info_helper, ingress_sw=s1, egress_sw=s2, tunnel_id=100,
                         dst_eth_addr="08:00:00:00:02:22", dst_ip_addr="10.0.2.2",SWITCH_TO_HOST_PORT=1,SWITCH_TO_SWITCH_PORT=2)

        writeTunnelRules(p4info_helper, ingress_sw=s2, egress_sw=s1, tunnel_id=200,
                         dst_eth_addr="08:00:00:00:01:11", dst_ip_addr="10.0.1.1",SWITCH_TO_HOST_PORT=1,SWITCH_TO_SWITCH_PORT=2)

        writeTunnelRules(p4info_helper, ingress_sw=s1, egress_sw=s3, tunnel_id=300,
                         dst_eth_addr="08:00:00:00:03:33", dst_ip_addr="10.0.3.3",SWITCH_TO_HOST_PORT=1,SWITCH_TO_SWITCH_PORT=3)

        writeTunnelRules(p4info_helper, ingress_sw=s3, egress_sw=s1, tunnel_id=400,
                         dst_eth_addr="08:00:00:00:01:11", dst_ip_addr="10.0.1.1",SWITCH_TO_HOST_PORT=1,SWITCH_TO_SWITCH_PORT=2)

        writeTunnelRules(p4info_helper, ingress_sw=s2, egress_sw=s3, tunnel_id=500,
                         dst_eth_addr="08:00:00:00:03:33", dst_ip_addr="10.0.3.3",SWITCH_TO_HOST_PORT=1,SWITCH_TO_SWITCH_PORT=3)

        writeTunnelRules(p4info_helper, ingress_sw=s3, egress_sw=s2, tunnel_id=600,
                         dst_eth_addr="08:00:00:00:02:22", dst_ip_addr="10.0.2.2",SWITCH_TO_HOST_PORT=1,SWITCH_TO_SWITCH_PORT=3)

        readTableRules(p4info_helper, s1)
        readTableRules(p4info_helper, s2)
        readTableRules(p4info_helper, s3)

        while True:
            sleep(2) #每两秒读一次隧道计数器
            print('\n----- Reading tunnel counters -----')
            print('\n ----- s1->s2 -----')
            printCounter(p4info_helper, s1, "MyIngress.ingressTunnelCounter", 100)
            printCounter(p4info_helper, s2, "MyIngress.egressTunnelCounter", 100)
            print('\n ----- s2->s1 -----')
            printCounter(p4info_helper, s2, "MyIngress.ingressTunnelCounter", 200)
            printCounter(p4info_helper, s1, "MyIngress.egressTunnelCounter", 200)
            print('\n ----- s1->s3 -----')
            printCounter(p4info_helper, s1, "MyIngress.ingressTunnelCounter", 300)
            printCounter(p4info_helper, s3, "MyIngress.egressTunnelCounter", 300)
            print('\n ----- s3->s1 -----')
            printCounter(p4info_helper, s3, "MyIngress.ingressTunnelCounter", 400)
            printCounter(p4info_helper, s1, "MyIngress.egressTunnelCounter", 400)
            print('\n ----- s2->s3 -----')
            printCounter(p4info_helper, s2, "MyIngress.ingressTunnelCounter", 500)
            printCounter(p4info_helper, s3, "MyIngress.egressTunnelCounter", 500)
            print('\n ----- s3->s2 -----')
            printCounter(p4info_helper, s3, "MyIngress.ingressTunnelCounter", 600)
            printCounter(p4info_helper, s2, "MyIngress.egressTunnelCounter", 600)
            print('\n----------- Finished -----------')

    except KeyboardInterrupt:
        print(" Shutting down.")
    except grpc.RpcError as e:
        printGrpcError(e)

    ShutdownAllSwitchConnections()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='P4Runtime Controller')
    parser.add_argument('--p4info', help='p4info proto in text format from p4c',
                        type=str, action="store", required=False,
                        default='./build/advanced_tunnel.p4.p4info.txt')
    parser.add_argument('--bmv2-json', help='BMv2 JSON file from p4c',
                        type=str, action="store", required=False,
                        default='./build/advanced_tunnel.json')
    args = parser.parse_args()

    if not os.path.exists(args.p4info):
        parser.print_help()
        print("\np4info file not found: %s\nHave you run 'make'?" % args.p4info)
        parser.exit(1)
    if not os.path.exists(args.bmv2_json):
        parser.print_help()
        print("\nBMv2 JSON file not found: %s\nHave you run 'make'?" % args.bmv2_json)
        parser.exit(1)
    main(args.p4info, args.bmv2_json)
