import xml.etree.ElementTree as ET
import os
from pathlib import Path

tree = ET.parse("config_routers.xml")
root = tree.getroot()

#création du dossier dynamips et vérification bgp
try :
    os.mkdir("/project-files/dynamips")
except : 
    print("Dynamips existe déjà")
bgp_enable = eval(root.attrib["bgp"])

for as_elem in root.findall("as"):

    as_number = int(as_elem.attrib["number"])
    rip_enable = eval(as_elem.attrib["rip"])
    ospf_enable = eval(as_elem.attrib["ospf"])
    ipv6_subnet = as_elem.attrib["ipv6_address_subnet"]
    ipv6_subnet_tab = ipv6_subnet.split(":")
    loopback_subnet = as_elem.attrib["loopback_subnet"]
    ipv6_prefix = ""

    for i in range(0, int(as_elem.attrib["ipv6_mask"]/16)+1) : 
        ipv6_prefix = ipv6_prefix + ipv6_subnet_tab[i] + ":"

    print(ipv6_prefix)

    print(f"rip : {rip_enable}")
    print(f"ospf : {ospf_enable}")
    #liste sans doublons de tous les réseaux qui existent dans l'as
    set_networks_as = set()
    #liste sans doublons de toutes les as avec lesquelles cette as partage une connexion ebgp
    set_remote_as = set()
    #nombre total de routers dans l'as
    how_many_routers = 0

    for router_elem in as_elem.findall("router"):
        how_many_routers +=1

    for router_elem in as_elem.findall("router"):

        #en partant du potulat qu'on nomme les routers("R{as_number}{router_num}. router_id correspond au numéro du router au niveau des configs. router_br indique si le router est de bordure ou pas")
        router_name = str(router_elem.attrib["name"])
        router_num = int(router_elem.attrib["num"])
        router_id = int((router_name[2:3])[0])
        router_br = False

        #buffer pour fichiers de config
        config_lines = []

#*******************************************************************préli et config @loopback******************************************************************************
        config_lines.append(f"version 15.2\nservice timestamps debug datetime msec\nservice timestamps log datetime msec\n!\nhostname {router_name}\n!\nboot-start-marker\nboot-end-marker\n!\nno aaa new-model\nno ip icmp rate-limit unreachable\nip cef\n!\nno ip domain lookup\nipv6 unicast-routing\nipv6 cef\n!\nmultilink bundle-name authenticated\n!\nip tcp synwait-time 5\n!\n!")
        config_lines.append(f"interface Loopback0\nno ip address\nnegotiation auto")

        config_lines.append(f"ipv6 address {loopback_subnet}{router_id}/128")
        config_lines.append(f"ipv6 enable")
        if rip_enable == True :
            config_lines.append(f"ipv6 rip ripng enable")
        if ospf_enable == True :
            config_lines.append(f"ipv6 ospf 100 area 1")
        config_lines.append(f"!")

#*******************************************************************config @ipv6 sur int correspondantes et activation rip/ospf*******************************************************************
        for neighbor_elem in router_elem.findall("neighbor"):
            
            neighbor_name = str(neighbor_elem.attrib["name"])
            neighbor_int = neighbor_elem.attrib["int"]

            #on veut que ca fonctionne en Fast et en Gigabit ethernet : 
            neighbor_int_tab = neighbor_int.split(" ")
            if str(neighbor_int_tab[0]) == "G" : 
                config_lines.append(f"interface GigabitEthernet{neighbor_int_tab[1]}/0")
            elif str(neighbor_int_tab[0]) == "F" : 
                config_lines.append(f"interface FastEthernet{neighbor_int_tab[1]}/0")
            config_lines.append(f"no ip address")

            #config_lines.append(f"negotiation auto")

            neighbor_id = int(([neighbor_name[2:3]])[0])

            #lesgo vérifier si le boug est un border router 
            neighbor_as_number = int(([neighbor_name[1:2]])[0])

            if neighbor_as_number == as_number : 
                if neighbor_id>router_id : 
                    set_networks_as.add(f"{router_id}{neighbor_id}")
                    config_lines.append(f"ipv6 address {ipv6_prefix}{router_id}{neighbor_id}::{router_id}/64")
                elif neighbor_id<router_id :  
                    set_networks_as.add(f"{neighbor_id}{router_id}")
                    config_lines.append(f"ipv6 address {ipv6_prefix}{neighbor_id}{router_id}::{router_id}/64")
            else : 
                router_br = True
                set_remote_as.add(neighbor_as_number)
                router_e_bgp_as = neighbor_as_number

#*******************************PAS CLAIR
                if int(router_id) == 6 :  
                    config_lines.append(f"ipv6 address 2003:192:168::{as_number}/64")
                elif int(router_id) == 7 :  
                    config_lines.append(f"ipv6 address 2004:192:168::{as_number}/64")
                    
            config_lines.append(f"ipv6 enable")
            if rip_enable == True :
                config_lines.append(f"ipv6 rip ripng enable")
            if ospf_enable == True :
                config_lines.append(f"ipv6 ospf 100 area 1")
            config_lines.append(f"!")

#*******************************************************************config bgp préli******************************************************************************************
        if bgp_enable == True : 
            config_lines.append(f"router bgp {as_number}")
            config_lines.append(f"bgp router {as_number}{router_id}.{as_number}{router_id}.{as_number}{router_id}.{as_number}{router_id}")
            config_lines.append(f"bgp log-neighbor-changes")
            config_lines.append(f"no bgp default ipv4-unicast")
            config_lines.append(f"redistribute connected")
    
#*******************************************************************bgp déclaration voisins*******************************************************************************
            for i in range(1,how_many_routers+1) :
                if(i==router_id) : 
                    continue
                else : 
                    config_lines.append(f"neighbor 200{as_number}:192:168::{i} remote-as {as_number}")
                    config_lines.append(f"neighbor 200{as_number}:192:168::{i} update-source Loopback0")

            if router_br==True : 
                config_lines.append(f"neighbor 200{router_e_bgp_as}:192:168::{router_id} remote-as {router_e_bgp_as}")
                config_lines.append(f"neighbor 200{router_e_bgp_as}:192:168::{router_id} ebgp-multihop 2")
                config_lines.append(f"neighbor 200{router_e_bgp_as}:192:168::{router_id} update-source Loopback0")

#*******************************************************************bgp address family***********************************************************************************
            config_lines.append(f"!\naddress-family ipv4\nexit-address-family\n!")
            config_lines.append(f"address-family ipv6")
            if router_br==True : 
                for i in set_networks_as : 
                    config_lines.append(f"network 200{as_number}:192:168:{i}::/64")

#***********************************A REFAIRE PROPRE
                if int(as_number) == 1 : 
                    #config_lines.append(f"network 2002:192:168::/48")
                    config_lines.append(f"network 2002:192:168::{router_id}/128")
                elif int(as_number) == 2 : 
                    #config_lines.append(f"network 2001:192:168::/48")
                    config_lines.append(f"network 2001:192:168::{router_id}/128")

                if {as_number} ==1 :
                    config_lines.append(f"network 2002:192:168::{router_id}/128")
                elif {as_number} ==2 :
                    config_lines.append(f"network 2001:192:168::{router_id}/128")
            
            
            for i in range(1,how_many_routers+1) :
                if(i==router_id) : 
                    continue
                else : 
                    config_lines.append(f"neighbor 200{as_number}:192:168::{i} activate")

            if router_br == True : 
                print(router_id)
            if router_br == True : 
                if as_number ==1 :
                    config_lines.append(f"neighbor 2002:192:168::{router_id} activate")
                elif as_number ==2 :
                    config_lines.append(f"neighbor 2001:192:168::{router_id} activate")
            config_lines.append("exit-address-family\n!")


#*******************************************************************suite en fin config************************************************************************************
        config_lines.append(f"ip forward-protocol nd\n!\nno ip http server\nno ip http secure-server\n!")

        #ipv6 route 2002:192:168::6/128 2003:192:168::2
        if router_br == True : 
            if int(as_number)==1 : 
                config_lines.append(f"ipv6 route 2002:192:168::{router_id}/128 2003:192:168::2")
            else : 
                config_lines.append(f"ipv6 route 2001:192:168::{router_id}/128 2003:192:168::1")


        if rip_enable == True :
            config_lines.append(f"ipv6 router rip ripng")
        if ospf_enable == True :
            config_lines.append(f"ipv6 router ospf 100\nrouter-id {router_id}.{router_id}.{router_id}.{router_id}")
        config_lines.append(f"!\ncontrol-plane\n!\nline con 0\nexec-timeout 0 0\nprivilege level 15\nlogging synchronous\nstopbits 1\nline aux 0\nexec-timeout 0 0\nprivilege level 15\nlogging synchronous\nstopbits 1\nline vty 0 4\nlogin\n!\nend")
        

#*******************************************************************écriture dans les fichiers******************************************************************************
# gns3 fy
        id_chelou = 0
        if router_num == 1 :
            id_chelou = "4a67a732-7e91-4a93-af11-bf8fa27d0cd4"
        elif router_num == 2 :
            id_chelou =  "ad2621ff-831a-494f-bfeb-cbfc1042b3cb"
        elif router_num == 3 :
            id_chelou =  "4d06e0f1-b740-4c3e-b030-e6fa258fe945"
        elif router_num == 4 :
            id_chelou =  "65e8760a-5418-436b-a17a-b1f807f02e47"
        elif router_num == 5 :
            id_chelou =  "b0b2af9b-b9d6-42d9-9bee-3949e7348f2c"
        elif router_num == 6 :
            id_chelou =  "9a442041-7ac5-4a47-89a8-de411512f0c8"
        elif router_num == 7 :
            id_chelou =  "a0a638d5-3c2e-4b51-9551-a01e9e9268a4"
        elif router_num == 8 :
            id_chelou =  "58bbb734-a7ef-4701-9068-c6c05b1a2f25"
        elif router_num == 9 :
            id_chelou =  "9c7341b7-25ba-430a-8fc1-8d7a5a808274"
        elif router_num == 10 :
            id_chelou =  "ddbe7890-8ca6-4bd8-b53b-53e3e2d1f0cc"
        elif router_num == 11 :
            id_chelou =  "27b63242-e173-4b12-b221-ed02fd2bbe6c"
        elif router_num == 12 :
            id_chelou =  "1b2f02d1-b1c2-4fb4-afde-4c55798bb8fc"
        elif router_num == 13 :
            id_chelou =  "868bcd3a-345f-4dba-8c6e-ad5d1ec9e639"
        elif router_num == 14 :
            id_chelou =  "a770ef93-f08a-4a76-b600-35d7d90ea9f7"

        path = os.getcwd()+"/project-files/dynamips/"+str(id_chelou)+"/configs"
        #print(path)
        #try :
            #os.mkdir(path, mode = 0o777)
        #except OSError as e : 
            #print(os.strerror(e.errno))

        path = path+"/i"+str(router_num)+"_startup-config.cfg"
        with open(path, "w") as config_file:
            config_file.write("\n".join(config_lines))
