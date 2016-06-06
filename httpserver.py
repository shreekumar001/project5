#!/usr/bin/python
import sys,urllib2,threading,commands,re,os
import BaseHTTPServer, SocketServer

global origin_name,server_port
#origin_name = "ec2-54-88-98-7.compute-1.amazonaws.com"
origin_port = 8080
#server_port = 45000

global cache_maxsize, memcache_size, diskcache_size, data_index, memdata_cache, cache_folder
cache_maxsize = 10000000
memcache_size = 0
diskcache_size = 0
data_index = []
memdata_cache = {}
cache_folder = "./cache"

infotodns_port = 45001

global filenum, file_database, diskdata_map
filenum = 1
file_database = []
diskdata_map = {}

#Get the Parameters
if len(sys.argv) == 5:
    if ("-o" in sys.argv) and ("-p" in sys.argv):
        origin_name = sys.argv[sys.argv.index("-o")+1]
        server_port = sys.argv[sys.argv.index("-p")+1]
        try:
            server_port = int(server_port)
        except:
            print "Port number is not right"
            sys.exit()
    else:
        print "Parameters are not enough"
        sys.exit()
else:
    print "The number of parameter is not right"
    sys.exit()

#Clear and create a folder on disk for cache
if os.path.exists(cache_folder):
    os.popen("rm -rf " + cache_folder)
os.makedirs(cache_folder)

#Set up a threading for handling measurment request from DNS
def get_latency(ipaddr):
    cmd = "scamper -c 'ping -c 1' -i " + ipaddr + " | awk 'END {print}'"
    try:
        res = commands.getoutput(cmd)
        delay_res = res.split("=")[1]
    except:
        print "Cannot get delay from scamper, give null"
        delay_avg = "null"
        return delay_avg
    delay_time = re.findall("\d+\.\d+",delay_res)
    if len(delay_time) == 4:
        delay_min,delay_avg,delay_max,delay_stddev = delay_time
    else:
        delay_avg = "null"
    return delay_avg

class MeasurementServer(SocketServer.TCPServer):
    allow_reuse_address = True

class MyTCPRequestHandler(SocketServer.BaseRequestHandler):
    def handle(self):
        ip_address = self.request.recv(256).strip()
        delay_avg = get_latency(ip_address)
        self.request.sendall(delay_avg)

class TCPSeverThread(threading.Thread):
    def __init__(self,infotodns_port):
        threading.Thread.__init__(self)
        self.infotodns_port = infotodns_port

    def run(self):
        mtcp_server = MeasurementServer(('',self.infotodns_port),MyTCPRequestHandler)
        mtcp_server.serve_forever()

#write a child class of BaseHTTPRequestHandler in BaseHTTPServer
class MyHTTPRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_GET(self):
        web_page = self.CacheManager(self.path)
        if web_page == 0:
            return
        else:
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(web_page)
        
    def CacheManager(self,path):
        global cache_maxsize, memcache_size, diskcache_size, data_index, memdata_cache, cache_folder
        global origin_name, origin_port
        global filenum, file_database, diskdata_map
        web_page = ""
        
        if memdata_cache.has_key(path):
            web_page = memdata_cache[path]
            add_page = [path,len(web_page)]
            data_index.pop(data_index.index(add_page))
            data_index.append(add_page)
            return web_page
        elif diskdata_map.has_key(path):
            filename = cache_folder + str(diskdata_map[path])
            file_pointer = open (filename,"r")
            web_page = file_pointer.read()
            add_page = [path,"disk",len(web_page)]
            data_index.pop(data_index.index(add_page))
            data_index.append(add_page)
            file_pointer.close()
            return web_page
        else:
            web_link = "http://" + origin_name + ":" + str(origin_port) + path
            try:
                print web_link
                web_page = urllib2.urlopen(web_link).read()
            except:
                self.send_error(404,"Not Found")
                return 0
            webpage_len = len(web_page)
            while 1:
                if (memcache_size + webpage_len) < cache_maxsize:
                    memcache_size += webpage_len
                    data_index.append([path,webpage_len])
                    memdata_cache[path] = web_page
                    return web_page
                elif (diskcache_size + webpage_len) < cache_maxsize:
                    diskcache_size += webpage_len
                    data_index.append([path,"disk",webpage_len])
                    if len(file_database) == 0:
                        diskdata_map[path] = filenum
                        filename = cache_folder + str(filenum)
                        filenum += 1
                    else:
                        filename = file_database.pop(0)
                        diskdata_map[path] = filename
                        filename = cache_folder + str(filename)
                    file_pointer = open(filename,"w")
                    file_pointer.write(web_page)
                    file_pointer.close()
                    return web_page
                else:
                    try:
                        del_page = data_index.pop(0)
                    except:
                        return web_page
                    if del_page[1] == "disk":
                        diskcache_size -= del_page[2]
                        filename = diskdata_map[del_page[0]]
                        del diskdata_map[del_page[0]]
                        file_database.append(filename)
                        os.remove(cache_folder + str(filename))
                    else:
                        memcache_size -= del_page[1]
                        del memdata_cache[del_page[0]]

#Run HTTP server
tcp_server = TCPSeverThread(infotodns_port)
tcp_server.start()
http_server = BaseHTTPServer.HTTPServer(('',server_port),MyHTTPRequestHandler)
http_server.serve_forever()

