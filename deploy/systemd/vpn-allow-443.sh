#!/bin/sh
# nginx serves the website AND the VPN SNI-splitter on :443. A leftover mtproxy
# firewall rule throttled NEW tcp/443 to 25/min/srcip then DROP, which strangled
# the VPN (many connections). mtproxy actually listens on 8443, so drop the 443
# jump and make sure 443 is accepted first.
iptables -D INPUT -p tcp --dport 443 -j MTPROXY_INPUT 2>/dev/null || true
iptables -C INPUT -p tcp --dport 443 -j ACCEPT 2>/dev/null || iptables -I INPUT 1 -p tcp --dport 443 -j ACCEPT
