import socket, time, argparse

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--b-ip", required=True, help="B machine IP, e.g., 192.168.1.20")
    ap.add_argument("--port", type=int, default=7001, help="B timecode port")
    ap.add_argument("--tc", default=None, help="timecode string, e.g., 00:00:10:12")
    args = ap.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # 你可以发“单次触发”，也可以按需连发几次提高可靠性
    tc = args.tc or time.strftime("%H:%M:%S", time.localtime())
    payload = f"TC {tc} {time.time_ns()}".encode("utf-8")  # 带一个ns时间戳方便日志里对齐

    for i in range(5):  # 连发5次，间隔10ms，抗丢包
        sock.sendto(payload, (args.b_ip, args.port))
        time.sleep(0.01)

    print("Sent:", payload.decode("utf-8"))

if __name__ == "__main__":
    main()
