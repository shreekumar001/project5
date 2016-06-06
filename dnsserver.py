#!/usr/bin/python

import sys,socket,random,struct,threading,urllib,urllib2,math,re,time

# Arguments from command line

port_no = int(sys.argv[1])
host_name = sys.argv[2]

# Replica Servers
replica_servers = {
'ec2-54-85-32-37.compute-1.amazonaws.com': '54.85.32.37',
'ec2-54-193-70-31.us-west-1.compute.amazonaws.com': '54.193.70.31',
'ec2-52-38-67-246.us-west-2.compute.amazonaws.com': '52.38.67.246',
'ec2-52-51-20-200.eu-west-1.compute.amazonaws.com': '52.51.20.200',
'ec2-52-29-65-165.eu-central-1.compute.amazonaws.com': '52.29.65.165',
'ec2-52-196-70-227.ap-northeast-1.compute.amazonaws.com': '52.196.70.227',
'ec2-54-169-117-213.ap-southeast-1.compute.amazonaws.com': '54.169.117.213',
'ec2-52-63-206-143.ap-southeast-2.compute.amazonaws.com': '52.63.206.143',
'ec2-54-233-185-94.sa-east-1.compute.amazonaws.com': '54.233.185.94'
};

# geo_location for the replica servers Hardcoded
geoCDN = {
'54.85.32.37': (39.044, -77.487),
'54.193.70.31': (37.775, -122.419),
'52.38.67.246': (45.523, -122.676),
'52.52.20.200': (53.344, -6.267),
'52.29.65.165': (50.116, 8.684),
'52.196.70.227': (35.690, 139.692),
'54.169.117.213': (1.290, 103.850),
'52.63.206.143': (-33.868, 151.207),
'54.233.185.94': (-23.548, -46.636)
};

# DNS STRUCTURE
# DNS header
#-------------------------------------
# transaction_id
# flags
# questions
# answer_RR
# authority_RR
# additional_RR

# Question Section
#-------------------------------------
# query_name
# query_type
# query_class

# Answer Section
#-------------------------------------
# response_name
# response_type
# response_class
# ttl
# response_length
# response_data

#Variable declarstion
result_rtt = []
global client_replica
global ti1,ti2
client_replica = {}

# To find geo IP location difference

def find_dist(lat_lon,loc):
        dtorad = math.pi/180.0
        lat1 = loc[0]
        lat2 = lat_lon[0]
        long1 = loc[1]
        long2 = lat_lon[1]
     
        l1 = (90.0 - lat1) * dtorad
        l2 = (90.0 - lat2) * dtorad
        n1 = long1 * dtorad
        n2 = long2 * dtorad
        c = (math.sin(l1) * math.sin(l2) * math.cos(n1 - n2) + math.cos(l1) * math.cos(l2))
        diff = math.acos(c)
        return diff

# To find RTT simultaneously using threads

class threads(threading.Thread):
        def __init__(self, host_ip,client_ip,test_port):
                threading.Thread.__init__(self)
                self.host_ip = host_ip
                self.client_ip = client_ip
                self.test_port = test_port
        def run(self):
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                
                try:
                        s.connect((self.host_ip,self.test_port))
                        s.sendall(self.client_ip)
                        RTT = s.recv(1024)
                except socket.error as code:
                        print "Error Code:",str(code)
                        RTT = ""
                #print "2"
                s.close()
                result_rtt.append([self.host_ip,float(RTT)])

# RTT for each replica using threading

def best_thread(return_ip):
        client_ip = return_ip
        host_ip = ""
        test_port = 45001
        #print "best thread called"
        thread_array = []
        thread_lock = threading.Lock()
        for host in replica_servers:
                host_ip = socket.gethostbyname(host)
                best_replica = threads(host_ip,client_ip,test_port)
                best_replica.start()
                #print best_replica
                thread_array.append(best_replica)
        for thread in thread_array:
                thread.join()

        #print thread_array
        sorted_rtt = sorted(result_rtt, key=lambda x:(x[1],x[0]))
        #print "sorted__________",sorted_rtt
        client_replica[client_ip] = sorted_rtt[0][0]
        #print client_replica

# To find best DNS server

def best_server(return_ip):
        
        client_ip = return_ip
        host_ip = ""
        
# Use Geo location to decide on the closest server first
        if client_ip not in client_replica:
                latency = {}
                geo_url = 'http://ip-api.com/json/'+client_ip
                #print geo_url
                for ip in geoCDN:
                        latency[ip] = 0
                        location = urllib2.urlopen(geo_url).read()
                        #print location
                        lat = float(re.findall('"lat":([+-]?\d+\.\d+)',location)[0])
                        lon = float(re.findall('"lon":([+-]?\d+\.\d+)',location)[0])
                        #print lat,lon
                        lat_lon = lat,lon
                        for ip,loc in geoCDN.iteritems():
                                latency[ip] = find_dist(lat_lon,loc)
                        response_ip = sorted(latency.items(), key=lambda x:x[1])

                return response_ip[0][0]
        else:
                        response_ip = client_replica[client_ip]
                        return response_ip

# parse the domain name to compare

def domain_converter(qname):
        i = 0
        dom_array = []
        while True:
                str_len = ord(qname[i])
                if (str_len != 0 ):
                        i = i + 1
                        dom_array.append(qname[i:i+str_len])
                        i = i + str_len
                else:
                        break
        s = "."
        qname = s.join(dom_array)
        
        return qname

# DNS request parsing and response construction

def dnsserver(query,return_ip):
        # extracting DNS query
	c_ip = return_ip[0]
        tx_id, flags, que_no, arec, nsrec, arrec = struct.unpack("!6H", query[:12])
        qname = query[12:-4]
        qtype,qclass = struct.unpack("!2H", query[-4:])

        # Converting the domain name from the query to cross check
        domain = domain_converter(qname)
	#print domain
	#print qtype
	#print host_name
        if ( qtype == 1 and domain == host_name ):
                que = que_no
                a_rec = 1
                for x in domain.split("."):
                        domain= "".join(chr(len(x)))
                domain+= "\x00"

                #constructing dns reply
                # DNS header
                flags = 0x8180
                questions = que_no
                A_RR = a_rec
                AU_RR = 0
                ADD_RR = 0

                dns_header = struct.pack("!6H", tx_id, flags, questions, A_RR, AU_RR, ADD_RR)

                # Question Section
                question_section = qname + struct.pack("!2H", qtype, qclass)

                # Answer Section
                response_name = 0xC00C
                response_type = 0x0001
                response_class = 0x0001
                ttl = 60
                data_length = 4
                address = best_server(c_ip)

                answer_section = struct.pack("!3HLH4s", response_name, response_type, response_class, ttl, data_length,socket.inet_aton(address))

                #DNS Response
                reply = dns_header + question_section + answer_section
                return reply
        else:
                print "DNS query failed"
                sys.exit()

# Creating a receive socket

# code starts here

try:
        recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        recv_sock.bind(('',port_no))
except socket.error as code:
        print "Error Code:",str(code)
        sys.exit(0)

while True:
        try:
                #print "waiting"
                ti1 = time.time()
                ti2 = ti1+180
                reply, return_ip = recv_sock.recvfrom(2048)
                if ti2 <= time.time():
            		client_replica.clear()
            		#print "after", client_replica
                response_data = dnsserver(reply,return_ip)
                recv_sock.sendto(response_data, return_ip)
                return_ip = return_ip[0]
            	#print return_ip
                best_thread(return_ip) 		# Get the RTT results simultaneously
        #recv_sock.settimeout(10)
        except KeyboardInterrupt:
            	recv_sock.close()
            	break

