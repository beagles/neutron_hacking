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

BRIDGE_NAME="qbr$BASE_ID"

# Create bridge if it doesn't exist
if ! [sudo ip link show $BRIDGE_NAME 2>/dev/null ];
then
    sudo brctl addbr $BRIDGE_NAME
    sudo brctl setfd $BRIDGE_NAME 0
    sudo brctl stp $BRIDGE_NAME off
    if test -e /sys/class/net/$BRIDGE_NAME/bridge/multicast_snooping;
    then
	echo 0 | sudo tee /sys/class/net/$BRIDGE_NAME/bridge/multicast_snooping
    fi
fi

VETH0="qvb$BASE_ID"
VETH1="qvo$BASE_ID"

if test "x$1" == "xplug";
then
    # TODO: error handling

    if ! [ ip link show $VETH1 2>/dev/null ];
    then
	sudo ip link delete $VETH0
	sudo ip link add $VETH0 type veth peer name $VETH1
	sudo ip link set $VETH0 up
	sudo ip link set $VETH0 promisc on
	sudo ip link set $VETH1 up
	sudo ip link set $VETH1 promisc on
	sudo ip link set $BRIDGE_NAME up
	sudo brctl addif $BRIDGE_NAME $VETH0
    fi

    sudo ovs-vsctl -- --if-exists del-port br-int $VETH1 -- add-port br-int $VETH1 --\
    set Interface $VETH1 external-ids:iface-id=$VIF_ID \
	external-ids:iface-status=active \
	external-ids:attached-mac=$VIF_MAC_ADDRESS \
	external-ids:vm-uuid=$VIF_INSTANCE_ID
fi

if test "x$1" == "xunplug";
then
    sudo brctl delif $BRIDGE_NAME $VETH0
    sudo ip link set $BRIDGE_NAME down
    sudo brctl delbr $BRIDGE_NAME
    sudo ovs-vsctl -- --if-exists del-port br-int $VETH1
fi
