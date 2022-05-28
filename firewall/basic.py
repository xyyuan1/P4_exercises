#!/usr/bin/env python3
import argparse
import grpc
import os
import sys
from time import sleep

sys.path.append(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 '../../utils/'))
import p4runtime_lib.bmv2
from p4runtime_lib.switch import ShutdownAllSwitchConnections
import p4runtime_lib.helper

def writeTunnelRules(p4info_helper, ingress_sw,port,dst_eth_addr, dst_ip_addr):

    table_entry = p4info_helper.buildTableEntry(
        table_name="MyIngress.ipv4_lpm",
        match_fields={
            "hdr.ipv4.dstAddr": (dst_ip_addr,32)
        },
        action_name="MyIngress.ipv4_forward",
        action_params={
            "dstAddr": dst_eth_addr,
            "port": port
        })

    ingress_sw.WriteTableEntry(table_entry)
    print("Installed egress tunnel rule on %s" % ingress_sw.name)
    print(dst_eth_addr,port)


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
    # Instantiate a P4Runtime helper from the p4info file
    p4info_helper = p4runtime_lib.helper.P4InfoHelper(p4info_file_path)

    try:
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
        s4 = p4runtime_lib.bmv2.Bmv2SwitchConnection(
            name='s4',
            address='127.0.0.1:50054',
            device_id=3,
            proto_dump_file='logs/s4-p4runtime-requests.txt')

        s2.MasterArbitrationUpdate()
        s3.MasterArbitrationUpdate()
        s4.MasterArbitrationUpdate()



        s2.SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                       bmv2_json_file_path=bmv2_file_path)
        print("Installed P4 Program using SetForwardingPipelineConfig on s2")
        s3.SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                       bmv2_json_file_path=bmv2_file_path)
        print("Installed P4 Program using SetForwardingPipelineConfig on s3")
        s4.SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                       bmv2_json_file_path=bmv2_file_path)
        print("Installed P4 Program using SetForwardingPipelineConfig on s4")



        writeTunnelRules(p4info_helper, ingress_sw=s2, port=4,dst_eth_addr="08:00:00:00:03:00", dst_ip_addr="10.0.1.1")

        writeTunnelRules(p4info_helper, ingress_sw=s2, port=3,dst_eth_addr="08:00:00:00:04:00", dst_ip_addr="10.0.2.2")

        writeTunnelRules(p4info_helper, ingress_sw=s2, port=1,dst_eth_addr="08:00:00:00:03:33", dst_ip_addr="10.0.3.3")

        writeTunnelRules(p4info_helper, ingress_sw=s2, port=2,dst_eth_addr="08:00:00:00:04:44", dst_ip_addr="10.0.4.4")


        writeTunnelRules(p4info_helper, ingress_sw=s3, port=1,dst_eth_addr="08:00:00:00:01:00", dst_ip_addr="10.0.1.1")

        writeTunnelRules(p4info_helper, ingress_sw=s3, port=1,dst_eth_addr="08:00:00:00:01:00", dst_ip_addr="10.0.2.2")

        writeTunnelRules(p4info_helper, ingress_sw=s3, port=2,dst_eth_addr="08:00:00:00:02:00", dst_ip_addr="10.0.3.3")

        writeTunnelRules(p4info_helper, ingress_sw=s3, port=2,dst_eth_addr="08:00:00:00:02:00", dst_ip_addr="10.0.4.4")


        writeTunnelRules(p4info_helper, ingress_sw=s4, port=2,dst_eth_addr="08:00:00:00:01:00", dst_ip_addr="10.0.1.1")

        writeTunnelRules(p4info_helper, ingress_sw=s4, port=2,dst_eth_addr="08:00:00:00:01:00", dst_ip_addr="10.0.2.2")

        writeTunnelRules(p4info_helper, ingress_sw=s4, port=1,dst_eth_addr="08:00:00:00:02:00", dst_ip_addr="10.0.3.3")

        writeTunnelRules(p4info_helper, ingress_sw=s4, port=1,dst_eth_addr="08:00:00:00:02:00", dst_ip_addr="10.0.4.4")

        readTableRules(p4info_helper, s2)
        readTableRules(p4info_helper, s3)
        readTableRules(p4info_helper, s4)
            

    except KeyboardInterrupt:
        print(" Shutting down.")
    except grpc.RpcError as e:
        printGrpcError(e)

    ShutdownAllSwitchConnections()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='P4Runtime Controller')
    parser.add_argument('--p4info', help='p4info proto in text format from p4c',
                        type=str, action="store", required=False,
                        default='./build/basic.p4.p4info.txt')
    parser.add_argument('--bmv2-json', help='BMv2 JSON file from p4c',
                        type=str, action="store", required=False,
                        default='./build/basic.json')
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
