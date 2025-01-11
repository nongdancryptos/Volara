import cloudscraper
import time
import docker
from datetime import datetime
from colorama import init, Fore, Style
from shareithub import shareithub

init(autoreset=True)

client = docker.from_env()

# Hàm để đọc token từ file
def read_token_from_file():
    try:
        with open('token.txt', 'r') as file:
            token = file.read().strip()
            return token
    except Exception as e:
        log_error(f"Đã xảy ra lỗi khi đọc token: {e}")
        return None

# Hàm để ghi log thông tin
def log_info(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{Fore.GREEN}[THÔNG BÁO] {timestamp} - {message}")

# Hàm để ghi log cảnh báo
def log_warning(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{Fore.YELLOW}[CẢNH BÁO] {timestamp} - {message}")

# Hàm để ghi log lỗi
def log_error(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{Fore.RED}[LỖI] {timestamp} - {message}")

# Hàm để lấy dữ liệu gas fee bằng cloudscraper
def fetch_gas_fee():
    url = "https://api.vanascan.io/api/v2/stats"
    try:
        scraper = cloudscraper.create_scraper()
        response = scraper.get(url)

        if response.status_code == 200:
            return response.json()  # Phân tích phản hồi JSON
        elif response.status_code == 403:
            log_warning("Không thể lấy dữ liệu: 403.")
            return None
        else:
            log_error(f"Không thể lấy dữ liệu: {response.status_code}")
            return None
    except Exception as e:
        log_error(f"Đã xảy ra lỗi: {e}")
        return None

# Hàm để lấy dữ liệu Volara
def fetch_volara_stats(token):
    url = "https://api.volara.xyz/v1/user/stats"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    try:
        scraper = cloudscraper.create_scraper()
        response = scraper.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()  
        else:
            log_error(f"Không thể lấy dữ liệu Volara: {response.status_code}")
            return None
    except Exception as e:
        log_error(f"Đã xảy ra lỗi khi lấy dữ liệu Volara: {e}")
        return None

# Hàm để liệt kê các container đang chạy
def list_running_containers():
    try:
        containers = client.containers.list()  
        if not containers:
            log_warning("Hiện không có container nào đang chạy.")
            return None

        log_info("Danh sách các container đang chạy:")
        for idx, container in enumerate(containers, start=1):
            image_tag = container.image.tags[0] if container.image.tags else 'Không có image'
            print(f"{idx}. {container.name} (Image: {image_tag})")
        
        choice = int(input("\nChọn số thứ tự của container bạn muốn giám sát: "))
        if choice < 1 or choice > len(containers):
            log_error("Lựa chọn không hợp lệ.")
            return None
        
        selected_container = containers[choice - 1]
        log_info(f"Bạn đã chọn container: {selected_container.name}")
        return selected_container
    except Exception as e:
        log_error(f"Đã xảy ra lỗi: {e}")
        return None

# Hàm để tạm dừng container
def pause_container(container):
    try:
        container_status = container.attrs['State']
        is_running = not container_status.get('Paused', False) and container_status.get('Running', False)

        if is_running:
            log_info(f"Tạm dừng container: {container.name}")
            container.pause()
            log_info(f"Container {container.name} đã được tạm dừng.")
        else:
            log_info(f"Container {container.name} đã ở trạng thái tạm dừng hoặc đã dừng.")
    except Exception as e:
        log_error(f"Đã xảy ra lỗi khi tạm dừng container: {e}")

# Hàm để tiếp tục container
def unpause_container(container):
    try:
        container_status = container.attrs['State']
        is_paused = container_status.get('Paused', False)

        if is_paused:
            log_info(f"Tiếp tục container: {container.name}")
            container.unpause()
            log_info(f"Container {container.name} đã được tiếp tục.")
        else:
            log_info(f"Container {container.name} không ở trạng thái tạm dừng, nên không cần tiếp tục.")
    except Exception as e:
        log_error(f"Đã xảy ra lỗi khi tiếp tục container: {e}")

def monitor_gas_fee_and_manage_docker(container, token, gas_fee_threshold_high=0.3, gas_fee_threshold_low=0.2):
    container_paused = False 

    while True:
        data = fetch_gas_fee()
        volara_data = fetch_volara_stats(token)

        if data:
            log_info("Trình theo dõi Gas Fee:")
            
            if 'gas_prices' in data:
                average_gas = data['gas_prices'].get('average', None)
                
                if average_gas is not None:
                    log_info(f"Gas Fee Trung Bình: {average_gas}")

                    if average_gas > gas_fee_threshold_high:
                        if not container_paused:
                            log_warning(f"Gas fee cao! Tạm dừng container.")
                            pause_container(container)
                            container_paused = True  
                        else:
                            log_info("Gas fee vẫn cao. Không có hành động bổ sung.")
                    elif average_gas < gas_fee_threshold_low:
                        if container_paused:
                            log_info("Gas fee thấp. Tiếp tục container.")
                            unpause_container(container)
                            container_paused = False
                        else:
                            log_info("Gas fee vẫn thấp. Không có hành động bổ sung.")
                    else:
                        log_info("Gas fee bình thường. Không thay đổi gì đối với container.")
                else:
                    log_warning("Không tìm thấy dữ liệu gas fee trung bình.")
            else:
                log_warning("Không tìm thấy dữ liệu gas_prices trong phản hồi.")
        else:
            log_warning("Không thể lấy dữ liệu gas fee.")

        if volara_data and volara_data.get("success"):
            log_info("\nDữ liệu Volara:")
            index_stats = volara_data.get('data', {}).get('indexStats', {})
            reward_stats = volara_data.get('data', {}).get('rewardStats', {})
            rank_stats = volara_data.get('data', {}).get('rankStats', {})

            total_indexed_tweets = index_stats.get("totalIndexedTweets", "Không có sẵn")
            vortex_score = reward_stats.get("vortexScore", "Không có sẵn")
            vortex_rank = rank_stats.get("vortexRank", "Không có sẵn")

            log_info(f"Tổng số Tweets đã được lập chỉ mục: {total_indexed_tweets}")
            log_info(f"Điểm Vortex: {vortex_score}")
            log_info(f"Hạng Vortex: {vortex_rank}")
        else:
            log_warning("Không thể lấy dữ liệu Volara hoặc phản hồi không thành công.")

        time.sleep(15)

shareithub()

def main():
    token = read_token_from_file()
    if not token:
        log_error("Không tìm thấy token. Chương trình dừng lại.")
        return

    try:
        gas_fee_threshold_high = float(input("Nhập ngưỡng cao cho gas fee để tạm dừng container (ví dụ: 0.3): "))
        gas_fee_threshold_low = float(input("Nhập ngưỡng thấp cho gas fee để tiếp tục container (ví dụ: 0.2): "))
    except ValueError:
        log_error("Giá trị ngưỡng gas fee không hợp lệ. Vui lòng nhập số thực.")
        return

    container = list_running_containers()
    if container:
        log_info(f"Bắt đầu giám sát cho container {container.name}...")
        monitor_gas_fee_and_manage_docker(container, token, gas_fee_threshold_high, gas_fee_threshold_low)

if __name__ == "__main__":
    main()
