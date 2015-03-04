#!/bin/bash
# 
# THIS IS JUST EXPERIMENTAL!!!!! OVS/linux bridge Hybrid Bridges is not a
# candidate for this stuff at this time.
#
# Expected environment variables.
# VIF_ID
# VIF_DEVNAME
# VIF_MAC_ADDRESS
# VIF_INSTANCE_ID

export PATH=/usr/sbin:/sbin:/usr/bin:/bin

BASE_ID="${VIF_ID:0:11}"

BRIDGE_NAME="qvb-$BASE_ID"

# Create bridge if it doesn't exist
if ! [ ip link show $BRIDGE_NAME 2>/dev/null ];
then
    brctl addbr $BRIDGE_NAME
    brctl addbr setfd $BRIDGE_NAME 0
    brctl stp $BRIDGE_NAME off
    if test -e /sys/class/net/$BRIDGE_NAME/bridge/multicast_snooping;
    then
	echo 0 | tee /sys/class/net/$BRIDGE_NAME/bridge/multicast_snooping
    fi
fi

VETH0="qvb-$BASE_ID"
VETH1="qvo-$BASE_ID"

# TODO: error handling

if ! [ ip link show $VETH1 2>/dev/null ];
then
    ip link delete $VETH0
    ip link add $VETH0 type veth peer name $VETH1
    ip link set $VETH0 up
    ip link set $VETH0 promisc on
    ip link set $VETH1 up
    ip link set $VETH1 promisc on
    ip link set $BRIDGE_NAME up
    brctl addif $BRIDGE_NAME $VETH0
fi

ovs-vsctl -- --if-exists del-port $VETH1 -- add-port br-int $VETH1 --\
    set Interface $VETH1 external-ids:iface-ids=$VIF_ID \
    external-ids:iface-status active \
    external-ids:attached-mac=$VIF_MAC_ADDRESS \
    external-ids:vm-uuid=$VIF_INSTANCE_ID

