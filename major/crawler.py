import requests
import json
import time
import csv
import os

# Define the URL and headers based on your request information.
# The URL is the endpoint that the POST request is sent to.
url = "https://zdbk.zju.edu.cn/jwglxt/xtgl/comm_cxPyfaZyxxList.html?rangeType=ggxydm&rangeable=false&gnmkdm=N153020&su=3220105108"

# Define the headers. It's crucial to include all headers from your request to mimic a real browser request.
# Pay special attention to 'Cookie', 'Referer', and 'User-Agent'.
headers = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Connection": "keep-alive",
    "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
    "Cookie": "JSESSIONPREJSDM=h%40Q%2CUB0Z%3AO%5EdJj%22%7BHZ8%5D1W0B0EF3Z%3AO%5E; JSESSIONID=D438B87E6E00B6B6BD5D33B21E783E06; _ga=GA1.1.1949979574.1733035698; device_token=f19ee27b9a78081a056429bfb8f16b6a; __root_domain_v=.zju.edu.cn; _qddaz=QD.497145223275758; Hm_lvt_35da6f287722b1ee93d185de460f8ba2=1749551386; _ga_H5QC8W782Q=GS2.1.s1751462357$o35$g1$t1751462402$j15$l0$h0; JSESSIONID=82CF1E7719032A2CF6A217E01CE8C0CE; route=c2c4d5a14bbc5b6918b307746d272ddd; _clck=10isy82%7C2%7Cfyh%7C0%7C2053; _ga_RHW3V3MQEE=GS2.1.s1755481366$o2$g0$t1755481366$j60$l0$h0; _csrf=S8mwplVi9KWoF2WQ0TlCeGQ1Mram2W%2FJweE2mkPXvoI%3D; _pv0=YUdqBldKSbJ1QboPC87VPoSKbXtK0RSAfIXUCnn4hA9A%2B0MMiGEg0uwQrVZvEEcVvsu1Qw1PR%2BsZ1pvUvlA3WehEEmDQy2NeCijM8TxQgXFbSqP29dNdOLzAyRXmS2yFTvAhb3HMHhTXrM8Br3n%2FparUcd6KR7lUZ9QLxHFaa2%2FZmDYqVvwQVi3%2FzN7o0BWMzgX2zB%2BxADBIkE3yBHBege5NEF4%2FPp%2FW99YwKOHt2RV8QN5o9dKdDYCH8EDQCrsyJdT2cthFuw8QaQaEUOSCyFWnmMJnbqDjyDO6X0gx0SGzD3pJdNMNOhteWObBbFIl8qvd%2Fgzz7Tr26oSdyAFNs5B19kzwSgXhBu3j5W6pRqjTCD7AWvbewJ0RCN1kgij8X4GOWgu8aEMKmzodN6DItDOh0K1keLsSeLH3LQX%2B0U0%3D; _pf0=OG9SpF8LuG5BXEOcuCXjFNnPM5E4i9Mg4HeQkj8wM0o%3D; _pc0=ST2AfUI021KXS4HQAAKSmBp90fS%2FuCKRkZSK%2FVUno%2F2QQNGW1N4PnyvEjsdtHpYP; iPlanetDirectoryPro=kKFhW9EennpdRYxKHfdpKnjEeTR51V4ZdvLKyV9wWWlohACFe4wBApiblu7DRdk0GH4wg0i%2BcK5XkBB%2FE8f0oMD%2F0JpEqNIjDQrduI9fwfMKFBN68ouN%2BWqnv8POUZ%2FUajskq1uUchI34VK7bvNNiC8wb96%2FHVxYXYL44ZW%2FSJvwOdlczg6c52WilXdhXxT874dN8ppMD1xSkmCWHwSQscF17Z6zHQpktyG6D2E1%2B03121BmG%2Fg59V8KeA1DHE9MvV2iNmxUNwkU4ZCdi44RNuEL%2F08wW9xvf8KLFEy4gZk5lE%2FJL18%2BPgU4mzio9Mh1nO8CMTbwl82gyL5bzvOWndM4I99i8IJuxD6qI703YdY%3D",
    "Host": "zdbk.zju.edu.cn",
    "Origin": "https://zdbk.zju.edu.cn",
    "Referer": "https://zdbk.zju.edu.cn/jwglxt/pyfagl/pyfaxxcx_cxPyfaxscxIndex.html?gnmkdm=N153020&layout=default&su=3220105108",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "sec-ch-ua": "\"Not;A=Brand\";v=\"24\", \"Chromium\";v=\"128\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"macOS\""
}

# The dictionary of departments and their corresponding IDs based on your provided list.
# This will be used to iterate through all departments.
departments = {
    "教务处": "00", "文学院": "41", "历史学院": "42", "哲学学院": "43", "外国语学院": "38",
    "传媒与国际文化学院": "25", "艺术与考古学院": "56", "经济学院": "01", "光华法学院": "A0",
    "教育学院": "03", "管理学院": "20", "公共管理学院": "24", "公共体育与艺术部": "48",
    "马克思主义学院": "55", "数学科学学院": "82", "物理学院": "32", "化学系": "77",
    "地球科学学院": "83", "心理与行为科学系": "79", "机械工程学院": "58",
    "材料科学与工程学院": "80", "能源工程学院": "59", "电气工程学院": "10",
    "建筑工程学院": "12", "化学工程与生物工程学院": "81", "海洋学院": "74",
    "航空航天学院": "26", "高分子科学与工程学系": "65", "光电科学与工程学院": "84",
    "信息与电子工程学院": "85", "控制科学与工程学院": "86", "计算机科学与技术学院": "21",
    "软件学院": "22", "生物医学工程与仪器科学学院": "15", "生命科学学院": "07",
    "生物系统工程与食品科学学院": "13", "环境与资源学院": "14", "农业与生物技术学院": "16",
    "动物科学学院": "17", "医学院": "18", "药学院": "19", "人文学院": "04",
    "外国语言文化与国际交流学院": "05", "国际教育学院": "23", "浙江大学爱丁堡大学联合学院": "27",
    "浙江大学伊利诺伊大学厄巴纳香槟校区联合学院": "28", "国际联合学院（海宁国际校区）": "29",
    "竺可桢学院": "30", "计算中心": "31", "校医院": "33", "信息技术中心": "34",
    "就业指导处": "36", "学工部": "37", "公体部": "40", "图书馆": "44", "人事处": "45",
    "国际设计研究院": "47", "中国西部发展研究院": "49", "出版社": "50",
    "思想政治理论教学科研部": "51", "心理健康教育与咨询中心": "52", "人武部": "53",
    "国际联合商学院": "57", "基础交叉研究院": "62", "临床医学系": "70",
    "口腔医学系": "71", "基础医学系": "72", "公共卫生系": "73", "物理学系": "76",
    "脑科学与脑医学系": "87", "求是学院": "90", "求是学院丹青学园": "91",
    "求是学院云峰学园": "92", "求是学院蓝田学园": "93", "农业试验站": "94",
    "实验室与设备管理处": "95", "本科生院": "98", "校共建专业": "99",
    "就业指导与服务中心": "U0", "工学部": "U1", "农业生命环境学部": "U2", "团委": "U3",
    "发展联络办公室": "U4", "国际合作与交流处": "U5", "港澳台事务办公室": "U6",
    "创新创业学院": "U7", "公共卫生学院": "U8", "社会学系": "U9"
}

# The base data for the POST request. The 'jg_id' will be updated in the loop.
base_data = {
    "njdm_id": "",
    "jg_id": ""
}

# Define the start and end years for the crawl.
start_year = 2025
end_year = 2025

# Loop through each year from start_year to end_year (inclusive).
for year in range(start_year, end_year - 1, -1):
    print(f"\n==================== 正在爬取 {year} 年的数据 ====================")
    
    # A list to store the final data rows for the current year's CSV.
    all_specialties_data = []

    # Add the header row to the data list.
    all_specialties_data.append(["教学计划号", "专业名称", "学院", "学院代码"])

    # Update the 'njdm_id' in the data payload for the current year.
    base_data["njdm_id"] = str(year)

    # Loop through each department in the dictionary.
    for dept_name, dept_id in departments.items():
        print(f"  正在为 {dept_name} ({dept_id}) 发送请求...")
        
        # Update the 'jg_id' in the data payload for the current department.
        base_data["jg_id"] = dept_id

        try:
            # Make the POST request.
            response = requests.post(url, headers=headers, data=base_data)
            
            # Check if the request was successful. A status code of 200 means success.
            if response.status_code == 200:
                try:
                    # The content is JSON, so we parse it into a Python dictionary.
                    json_data = response.json()
                    print(f"  {dept_name} 请求成功！")

                    # The response is a list of dictionaries.
                    # Iterate through each dictionary to extract the required data.
                    if isinstance(json_data, list):
                        for item in json_data:
                            # Extract specialty code and name.
                            zydm = item.get("zydm", "")
                            zymc = item.get("zymc", "")
                            
                            # Construct the teaching plan number (教学计划号) as Year + specialty code.
                            if zydm:
                                teaching_plan_id = str(year) + zydm
                            else:
                                teaching_plan_id = ""

                            # Append the extracted information to the data list.
                            all_specialties_data.append([
                                teaching_plan_id,
                                zymc,
                                dept_name,
                                dept_id
                            ])
                    
                except json.JSONDecodeError:
                    print(f"  {dept_name} 请求成功，但响应不是有效的 JSON。")
                    print("  --- 响应内容 ---")
                    print(response.text)
            else:
                # If the status code is not 200, print the error and response text.
                print(f"  {dept_name} 请求失败，状态码：{response.status_code}")
                print("  --- 错误详情 ---")
                print(response.text)
            
            # Add a small delay to avoid overwhelming the server with requests.
            time.sleep(0.5)

        except requests.exceptions.RequestException as e:
            # Handle any network-related errors, like connection issues.
            print(f"  为 {dept_name} 发生网络错误: {e}")

    # Define the output CSV file name for the current year.
    output_file = f"specialties_data_{year}.csv"

    # Write the collected data to a CSV file.
    try:
        with open(output_file, 'w', newline='', encoding='utf-8-sig') as file:
            writer = csv.writer(file)
            writer.writerows(all_specialties_data)
        print(f"\n数据已成功写入到 {os.path.abspath(output_file)} 文件中。")
    except IOError as e:
        print(f"\n写入文件时发生错误: {e}")

