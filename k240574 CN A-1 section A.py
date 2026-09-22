import socket
import struct
import random

def build_dns_query(domain_name, transaction_id):
    # header section
    # recursion desired = 1 : 0x0100
    flags = 0x0100
    q_count = 1  # 1 question
    a_count = 0  # 0 answers
    ns_count = 0  # 0 Name server
    ar_count = 0  # 0 Additional records
    
    header = struct.pack("!HHHHHH", transaction_id, flags, q_count, a_count, ns_count, ar_count)


    # question section encoding: "www.example.com" -> \x03www\x07example\x03com\x00
    qname = b""  # bytes object
    for part in domain_name.split('.'):
        qname += bytes([len(part)]) + part.encode('utf-8')
    qname += b"\x00"  #terminating null byte

    qtype = 1   # type A
    qclass = 1  # class IN(internet)
    
    question = qname + struct.pack("!HH", qtype, qclass)
    return header + question


def parse_domain_name(response, offset):
    # Get domain names from response bytes
    
    labels = []
    jumped = False
    original_offset = offset

    while True:
        length = response[offset]

        # check for DNS name compression(top 2 bits set: 11xxxxxx = 0xC0)
        if (length & 0xC0) == 0xC0:
            if not jumped:
                original_offset = offset + 2
                jumped = True
            # get offset pointer from the 14 remaining bits
            pointer = struct.unpack("!H", response[offset:offset+2])[0] & 0x3FFF
            offset = pointer
        elif length == 0:
            offset += 1
            break
        else:
            offset += 1
            labels.append(response[offset:offset+length].decode('utf-8', errors='replace'))
            offset += length

    final_offset = original_offset if jumped else offset
    return ".".join(labels), final_offset


def parse_dns_response(response, expected_tx_id):   
    # Get the raw binary response and displays required DNS fields.
    
    # Get Header
    tx_id, flags, q_count, a_count, ns_count, ar_count = struct.unpack("!HHHHHH", response[:12])
    
    # Extract Response Code from flags
    rcode = flags & 0x000F
    rcode_messages = {
        0: "NoError (Success)",
        1: "FormErr (Format Error)",
        2: "ServFail (Server Failure)",
        3: "NXDomain (Non-Existent Domain)",
        4: "NotImp (Not Implemented)",
        5: "Refused"
    }
    
    status_str = rcode_messages.get(rcode, f"Unknown Error ({rcode})")

    print("\n--- DNS Header Parsing ---")
    print(f"Transaction ID : 0x{tx_id:04X}")
    print(f"Response Status: {status_str}")
    print(f"Answer Count   : {a_count}")

    if rcode != 0:
        print(f"\n[!] Query Unsuccessful: {status_str}")
        return

    offset = 12

    for _ in range(q_count):
        _, offset = parse_domain_name(response, offset)
        offset += 4  # Skip QTYPE and QCLASS(questions)

    # Parse Answer Section
    print("\n--- Answer Records ---")
    if a_count == 0:
        print("No answer records returned.")
        return

    found_a_record = False
    for i in range(a_count):
        name, offset = parse_domain_name(response, offset)
        rtype, rclass, ttl, rdlength = struct.unpack("!HHIH", response[offset:offset+10])
        offset += 10
        rdata = response[offset:offset+rdlength]
        offset += rdlength

        if rtype == 1:  # Type A
            ip_address = ".".join(str(byte) for byte in rdata)
            print(f"Record {i+1}:")
            print(f"  Domain Name : {name}")
            print(f"  Type        : A")
            print(f"  TTL         : {ttl}s")
            print(f"  IP Address  : {ip_address}")
            found_a_record = True
        else:
            print(f"Record {i+1}: Type {rtype} (non-A record), TTL: {ttl}")

    if not found_a_record:
        print("No A records found in the answer section.")


def query_dns(domain_name, dns_server):
    #Sends DNS query via UDP socket to port 53 and manages timeouts.
    
    transaction_id = random.randint(0, 65535)
    query_packet = build_dns_query(domain_name, transaction_id)

    # setup UDP Socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(3.0)  # 3-second timeout

    try:
        print(f"\nSending DNS Query for '{domain_name}' to server [{dns_server}:53]...")
        sock.sendto(query_packet, (dns_server, 53))
        
        response, _ = sock.recvfrom(1024)
        parse_dns_response(response, transaction_id)

    except socket.timeout:
        print(f"\n[!] Error: Request to DNS server '{dns_server}' timed out.")
    except socket.gaierror:
        print(f"\n[!] Error: Provided DNS server IP address '{dns_server}' is invalid.")
    finally:
        sock.close()


def main():
    print("=================== Custom Raw UDP DNS Query Client ===================")

    # Get DNS Server Address once
    dns_server = input("Enter DNS Server IP Address (e.g. 1.1.1.1): ").strip()

    #MAIN lookup loop
    while True:
        domain_name = input("Enter domain name to resolve (or 'exit' to quit): ").strip()
        
        if domain_name.lower() == 'exit':
            print("Exiting program")
            break
            
        if not domain_name:
            print("Domain name cannot be empty")
            continue

        query_dns(domain_name, dns_server)


if __name__ == "__main__":
    main()