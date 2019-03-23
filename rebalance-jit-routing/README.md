# Rebalance Plugin for JIT Routing

This script is WORK IN PROGRESS and not fully running yet.

The goal is to have a simple channel rebalancing plugin for c-lightning which can also be extended for JIT Routing (c.f.: https://lists.linuxfoundation.org/pipermail/lightning-dev/2019-March/001891.html )

The code has not been wrapped to the c-lightning plugin api. also there are currently dependancies to local files (which can be extracted from `lightning-cli` api calls.

Overall as mentioned this script is work in progress. since I will not be working on it for the next 3 months I decided to publish the unfinnished script in case anyone wants to build on top of it.

once finnished run the plugin with:

```
lightningd --plugin=/path/to/c-lightning-plugin-collection/simpleFundsOverview/rebalance.py
```

## About the plugin
This plugin was created and is maintained by Rene Pickhardt. It shall serve as
an educational resource on his Youtube channel at:

https://www.youtube.com/user/RenePickhardt

The plugin is licensed like the rest of c-lightning with BSD-MIT license
and comes without any warrenty (see LICENSE file)

If you like my work feel free to support me on patreon:
https://www.patreon.com/renepickhardt

Or support the crowdfunding campaign of my book project about the lightning network at:
https://tallyco.in/s/lnbook/

or leave me a tip on my donation page (comming from the donation plugin):
https://ln.rene-pickhardt.de/

The work was partially sponsored by http://fulmo.org/
