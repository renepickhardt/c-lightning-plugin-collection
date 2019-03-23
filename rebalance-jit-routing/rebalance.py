from lightning import LightningRpc
from operator import itemgetter

import json
import networkx as nx


class Network:
    """ retrieves the lightning network and provides a pruned view of the extended ego network

    """

    def __compute_friends(self):
        self.__friends = set(channel["peer_id"]
                             for channel in self.__own_channels)
        print(len(self.__friends))

    def __compute_pruned_extended_egonetwork(self):
        """ Computes the friend of a friend network without own channels

        """
        foaf_network = []
        for u, v in self.__lightning_network.edges():
            channel = self.__lightning_network[u][v]
            if channel["source"] in self.__friends or channel["destination"] in self.__friends:
                foaf_network.append(self.__lightning_network[u][v])

        peer_counter = {}
        for channel in foaf_network:
            src = channel["source"]
            if src not in peer_counter:
                peer_counter[src] = 1
            else:
                peer_counter[src] += 1

        to_remove = set(
            key for key, value in peer_counter.items() if value == 1)

        # node_ids = set(k for k, v in peer_counter.items() if v > 1)
        # print(len(node_ids))

        final_ego_network = []
        for channel in foaf_network:
            src = channel["source"]
            dest = channel["destination"]
            if src == self.__own_node_id or dest == self.__own_node_id:
                continue
            if src not in to_remove and dest not in to_remove:
                final_ego_network.append(channel)

        self.__pruned_ln = nx.DiGraph()
        for channel in final_ego_network:
            self.__pruned_ln.add_edge(
                channel["source"], channel["destination"], **channel)

        # print(len(foaf_network))
        # print(len(final_ego_network))

    def __init__(self, network, own_channels, node_id):
        print("initialized the Network maintainer")
        self.__own_node_id = node_id
        self.__lightning_network = nx.DiGraph()
        for channel in network:
            self.__lightning_network.add_edge(
                channel["source"], channel["destination"], **channel)
        self.__own_channels = own_channels
        self.__compute_friends()
        self.__compute_pruned_extended_egonetwork()

    def get_pruned_network(self):
        return self.__pruned_ln

    def get_full_network(self):
        return self.__lightning_network


class EgoNetwork():

    def __init__(self, own_channels):
        self.__channels = {}
        for channel in own_channels:
            self.__channels[channel["peer_id"]] = channel

    def liquidity_stats(self, node_id):
        channel = self.__channels[node_id]
        ours = int(channel["channel_sat"])
        cap = int(channel["channel_total_sat"])
        rel = float(ours)/float(cap)
        return "us:{:10} total:{:10} relative: {:4.2f}".format(ours, cap, rel)


class ChannelSuggester():
    """ checks the balances of channels and suggest to rebalance

    FIXME: could go a way from relative boundaries and always work on top / flop channels
    """

    def __get_sorted_channels(self):
        channel_list = []
        for channel in self.__local_channels:
            channel_sat = int(channel["channel_sat"])
            channel_total_sat = int(channel["channel_total_sat"])
            channel_list.append(
                (float(channel_sat)/float(channel_total_sat), channel))
        channel_list.sort(key=itemgetter(0))
        return channel_list

    def __init__(self, local_channels_with_balance, min_incoming_capacity=0.01, max_outgoing_capacity=0.99):
        print("initialized the channel suggester")
        self.__local_channels = local_channels_with_balance
        self.__min_incoming_capacity = min_incoming_capacity
        self.__max_outgoing_capacity = max_outgoing_capacity

    def is_need_to_balance(self):
        channels = self.__get_sorted_channels()
        if len(channels) < 2:
            print("not enough channels to do a balancing operation")
            return False
        if channels[0][0] > self.__min_incoming_capacity:
            print("not enough incomming capacity to rebalance")
            return False
        if channels[-1][0] < self.__max_outgoing_capacity:
            print("not enough outgoing capacity to rebalance")
            return False
        return True

    def get_dry_channels(self):
        channels = [chan for chan in self.__get_sorted_channels(
        ) if chan[0] < self.__min_incoming_capacity]
        return channels

    def get_liquid_channels(self):
        channels = [chan for chan in self.__get_sorted_channels(
        ) if chan[0] > self.__max_outgoing_capacity]
        return channels


class PeerAnalyzer():

    def __list_channel_ratios(self, offered_str, fulfilled_str):
        for peer in self.__peers:
            for channel in peer["channels"]:
                offered = int(channel[offered_str])
                if offered > 0:
                    fulfilled = int(channel[fulfilled_str])
                    print("{:4.2f}\t{}\t{}".format(float(fulfilled)/offered,
                                                   offered, fulfilled), channel["channel_id"], channel["short_channel_id"])

    def __list_in_ratios(self):
        print("inratios")
        self.__list_channel_ratios(
            "in_payments_offered", "in_payments_fulfilled")
        print("")

    def __list_out_ratios(self):
        print("outratios")
        self.__list_channel_ratios(
            "out_payments_offered", "out_payments_fulfilled")
        print()

    def __init__(self):
        f = open("/Users/rpickhardt/hacken/plugindev/peers20190310.json", "r")
        jsn = json.load(f)
        self.__peers = jsn["peers"]
        self.__list_in_ratios()
        self.__list_out_ratios()


class CycleSuggester():
    def __init__(self, network):
        self.__network = network

    def paths(self, start, end):
        return list(nx.all_simple_paths(self.__network, start, end, 3))


class FeeCalculator():

    def __node_id_path_to_channels(self, path):
        channels = []
        for i in range(len(path)-1):
            src = path[i]
            dest = path[i+1]
            channel = self.__network[src][dest]
            channels.append(channel)
            # print(channel)
        return channels

    def __onion_from_channels(self, amount, channels):
        route = []
        item = {}
        item["msatoshi"] = amount
        item["channel"] = channels[-1]["short_channel_id"]
        # FIXME: how can we know this for abitrary cases?
        item["delay"] = 10
        item["id"] = channels[-1]["destination"]
        route.append(item)
        for i in range(len(channels)-1, 0, -1):
            old = route[-1]
            item = {}
            item["msatoshi"] = old["msatoshi"] + \
                int(channels[i]["base_fee_millisatoshi"]) + old["msatoshi"] * \
                int(channels[i]["fee_per_millionth"]) // 1000000
            item["channel"] = channels[i-1]["short_channel_id"]
            item["delay"] = old["delay"] + int(channels[i]["delay"])
            item["id"] = channels[i]["source"]
            route.append(item)
        return list(reversed(route))

    def __init__(self, network):
        self.__network = network

    def compute_fee_for_path(self, amount, path):
        channels = self.__node_id_path_to_channels(path)
        onion_route = self.__onion_from_channels(amount, channels)
        return onion_route[0]["msatoshi"] - amount
        # print(onion_route)


if __name__ == "__main__":
    pa = PeerAnalyzer()
    exit()
    ln = LightningRpc("/home/rpickhardt/.lightning/lightning-rpc")
    own_channels = None
    try:
        f = open(
            "/Users/rpickhardt/hacken/lightning-helpers/balance-channels/friends20190301.json")
        own_channels = json.load(f)["channels"]
    except:
        own_channels = ln.listfunds()["channels"]

    ego_network = EgoNetwork(own_channels)

    channel_suggester = ChannelSuggester(own_channels, 0.25, 0.5)
    if channel_suggester.is_need_to_balance():
        print("channel balancing is suggested")
        # print("channels with too little outgoing capacity:")
        # for chan in channel_suggester.get_dry_channels():
        #    print(chan)
        print("channels with too little incoming capacity:")
        for chan in channel_suggester.get_liquid_channels():
            print(chan)

    channels = None
    try:
        f = open(
            "/Users/rpickhardt/hacken/lightning-helpers/balance-channels/channels20190301.json")
        channels = json.load(f)["channels"]
    except:
        channels = ln.listchannels()["channels"]

    own_node_id = "03efccf2c383d7bf340da9a3f02e2c23104a0e4fe8ac1a880c8e2dc92fbdacd9df"
    network = Network(channels, own_channels, own_node_id)
    print(len(channels))

    sug = CycleSuggester(network.get_pruned_network())
    # sug = CycleSuggester(network.get_full_network())

    flag = False
    fee_calculator = FeeCalculator(network.get_full_network())
    for source in channel_suggester.get_liquid_channels():
        for dest in channel_suggester.get_dry_channels():
            try:
                src = source[1]["peer_id"]
                dest = dest[1]["peer_id"]
                # print(src, dest)
                paths = sug.paths(src, dest)
                if len(paths) == 0:
                    continue
                minfee = 10000000
                bpath = None
                for p in paths:
                    path = [own_node_id]
                    path.extend(p)
                    path.append(own_node_id)
                    fee = fee_calculator.compute_fee_for_path(100000000, path)
                    if fee < minfee:
                        minfee = fee
                        bpath = path
                print(minfee, bpath)
                # sat = network.get_full_network()
                # print(sat[src][dest])
                # sat = sat[src][dest]["channel_sat"]
                # cap = network.get_pruned_network(
                # )[src][dest]["channel_total_sat"]
                f_stats = ego_network.liquidity_stats(src)
                t_stats = ego_network.liquidity_stats(dest)
                print("found {:6} paths from {} with {}  to {} with {} ".format(
                    len(paths), src, f_stats, dest, t_stats))
                # flag = True
            except Exception as e:
                # print(e)
                # print(source, dest)
                pass
            if flag:
                break
        print()
        if flag:
            break

    path = [own_node_id, "03c4bb19c3a388d790968328b0f0d187a1a28597d3ad082200a47baadfdb6aee8d",
            "020e56a13babec99abdc2c4afbe34e1e44230d79b234c059fd4ff1e367765fdb1b",
            "02e2670a2c2661a9eea13b7cfdcdd7f552f591b9ee60e5678b7abe77b7f9516f96",
            "03ee180e8ee07f1f9c9987d98b5d5decf6bad7d058bdd8be3ad97c8e0dd2cdc7ba"]
    print(fee_calculator.compute_fee_for_path(1000000, path))
    # print(sug.paths(channel_suggester.get_liquid_channels()
    #                [-1], channel_suggester.get_dry_channels()[0]))
