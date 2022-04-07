#!/usr/bin/env python3
import argparse
import grpc
import os
import sys
from time import sleep

#导入库和函数
sys.path.append(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 '../../utils/'))
import p4runtime_lib.bmv2
from p4runtime_lib.switch import ShutdownAllSwitchConnections
import p4runtime_lib.helper

#写交换机静态规则
def writeRules(p4info_helper, egress_sw,port,dst_eth_addr, dst_ip_addr,port):
    table_entry = p4info_helper.buildTableEntry(
        table_name="MyIngress.ipv4_lpm",
        match_fields={
            "hdr.ipv4.dstAddr": (dst_ip_addr, port)
        },
        action_name="MyIngress.ipv4_forward",
        action_params={
            "dstAddr": dst_eth_addr,
            "port": port
        })

    egress_sw.WriteTableEntry(table_entry)
    print("Installed egress tunnel rule on %s" % egress_sw.name)

#读入table规则
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

def printGrpcError(e):
    print("gRPC Error:", e.details(), end=' ')
    status_code = e.code()
    print("(%s)" % status_code.name, end=' ')
    traceback = sys.exc_info()[2]
    print("[%s:%d]" % (traceback.tb_frame.f_code.co_filename, traceback.tb_lineno))

#主函数
def main(p4info_file_path, bmv2_file_path):
    #实例化一个p4runtime helper
    p4info_helper = p4runtime_lib.helper.P4InfoHelper(p4info_file_path)
    #创建三个交换机连接
    try:
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

        s1.MasterArbitrationUpdate()
        s2.MasterArbitrationUpdate()
        s3.MasterArbitrationUpdate()

        s1.SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                       bmv2_json_file_path=bmv2_file_path)
        print("Installed P4 Program using SetForwardingPipelineConfig on s1")
        s2.SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                       bmv2_json_file_path=bmv2_file_path)
        print("Installed P4 Program using SetForwardingPipelineConfig on s2")
        s3.SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                       bmv2_json_file_path=bmv2_file_path)
        print("Installed P4 Program using SetForwardingPipelineConfig on s3")
        
        #动态改写规则
        writeRules(p4info_helper,egress_sw=s1, port=2,dst_eth_addr="08:00:00:00:01:01", dst_ip_addr="10.0.1.1", port=32)
        writeRules(p4info_helper, egress_sw=s1, port=1,dst_eth_addr="08:00:00:00:01:11", dst_ip_addr="10.0.1.11", port=32)
        writeRules(p4info_helper, egress_sw=s1, port=3,dst_eth_addr="08:00:00:00:02:00", dst_ip_addr="10.0.2.0", port=24)
        writeRules(p4info_helper, egress_sw=s1, port=4,dst_eth_addr="08:00:00:00:03:00", dst_ip_addr="10.0.3.0", port=24)

        writeRules(p4info_helper, egress_sw=s2, port=2,dst_eth_addr="08:00:00:00:02:02", dst_ip_addr="10.0.2.2", port=32)
        writeRules(p4info_helper, egress_sw=s2, port=1,dst_eth_addr="08:00:00:00:02:22", dst_ip_addr="10.0.2.22", port=32)
        writeRules(p4info_helper, egress_sw=s2, port=3,dst_eth_addr="08:00:00:00:01:00", dst_ip_addr="10.0.1.0", port=24)
        writeRules(p4info_helper, egress_sw=s2, port=4,dst_eth_addr="08:00:00:00:03:00", dst_ip_addr="10.0.3.0", port=24)


        writeRules(p4info_helper, egress_sw=s3, port=1,dst_eth_addr="08:00:00:00:03:03", dst_ip_addr="10.0.3.3", port=32)
        writeRules(p4info_helper, egress_sw=s3, port=2,dst_eth_addr="08:00:00:00:01:00", dst_ip_addr="10.0.1.0", port=24)
        writeRules(p4info_helper, egress_sw=s3, port=3,dst_eth_addr="08:00:00:00:02:00", dst_ip_addr="10.0.2.0", port=24)


        readTableRules(p4info_helper, s1)
        readTableRules(p4info_helper, s2)
        readTableRules(p4info_helper, s3)
            

    except KeyboardInterrupt:
        print(" Shutting down.")
    except grpc.RpcError as e:
        printGrpcError(e)

    ShutdownAllSwitchConnections()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='P4Runtime Controller')
    parser.add_argument('--p4info', help='p4info proto in text format from p4c',
                        type=str, action="store", required=False,
                        default='./build/ecn.p4.p4info.txt')
    parser.add_argument('--bmv2-json', help='BMv2 JSON file from p4c',
                        type=str, action="store", required=False,
                        default='./build/ecn.json')
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
