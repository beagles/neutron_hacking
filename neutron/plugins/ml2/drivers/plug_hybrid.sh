#!/bin/bash
#
# Expected environment variables.
# OS_VIF_ID
# OS_INTEGRATION_BRIDGE_NAME
# OS_BRIDGE_NAME
# OS_VIF_ADDRESS
# OS_MAC_ADDRESS
# OS_INSTANCE_ID
# OS_MTU

# Create bridge if it doesn't exist
if ! [ ip link show $OS_BRIDGE_NAME 2>/dev/null ];
then
    brctl addbr $OS_BRIDGE_NAME
    brctl addbr setfd $OS_BRIDGE_NAME 0
    brctl stp $OS_BRIDGE_NAME off
    echo 0 | tee /sys/class/net/$OS_BRIDGE_NAME/bridge/multicast_snooping
fi

VETH0="qvb-$OS_VIF_ID"
VETH1="qvo-$OS_VIF_ID"

# TODO: error handling

if ! [ ip link show $VETH1 2>/dev/null ];
then
    ip link delete $VETH0
    ip link add $VETH0 type veth peer name $VETH1
    ip link set $VETH0 up
    ip link set $VETH0 promisc on
    ip link set $VETH1 up
    ip link set $VETH1 promisc on
    ip link set $OS_BRIDGE_NAME up
    brctl addif $OS_BRIDGE_NAME $ETH0
fi

ovs-vsctl -- --if-exists del-port $VETH1 -- add-port $OS_INTEGRATION_BRIDGE_NAME $VETH1 --\
    set Interface $VETH1 external-ids:iface-ids=$OVS_VIF_ID \
    external-ids:iface-status active \
    external-ids:attached-mac=$OS_MAC_ADDRESS \
    external-ids:vm-uuid=$OS_INSTANCE_ID

# TODO: error code?
ip link set $VETH1 mtu $OS_MTU
