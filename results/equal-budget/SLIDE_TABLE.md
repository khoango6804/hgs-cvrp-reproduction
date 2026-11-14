# HGS và Set Partitioning dưới cùng ngân sách CPU

Trên 8 instance, gap của nghiệm tốt nhất qua 10 seed trung bình là 0.1015% với HGS và 0.1006% với HGS + Set Partitioning. Bản hybrid thắng 2, hòa 5 và thua 1 instance.

| Instance | Ngân sách CPU (giây) | Gap HGS best-of-10 | Gap HGS + SP | Δ gap (điểm %) |
|---|---:|---:|---:|---:|
| X-n101-k25 | 2,400 | 0.0000% | 0.0000% | +0.0000 |
| X-n157-k13 | 3,750 | 0.0000% | 0.0000% | +0.0000 |
| X-n251-k28 | 6,000 | 0.0000% | 0.0000% | +0.0000 |
| X-n401-k29 | 9,600 | 0.0771% | 0.0771% | +0.0000 |
| X-n502-k39 | 12,030 | 0.0188% | 0.0058% | -0.0130 |
| X-n627-k43 | 15,030 | 0.1705% | 0.1641% | -0.0064 |
| X-n801-k40 | 19,200 | 0.1050% | 0.1173% | +0.0123 |
| X-n1001-k43 | 24,000 | 0.4409% | 0.4409% | +0.0000 |
| **Trung bình** | | **0.1015%** | **0.1006%** | **-0.0009** |

Δ gap = gap HGS + SP trừ gap HGS. Giá trị âm là cải thiện. Hai nhánh dùng cùng BKS năm 2020.

Baseline dùng 10 lượt HGS đã hoàn tất trên cùng máy WSL. Với mỗi instance, ngân sách là `10 × T`, với `T = ceil(2,4 × số khách)`. Bản hybrid chạy lại cùng binary và seed 1–10 với `T − 1` giây CPU mỗi seed. Ngân sách còn lại dành cho đọc và kiểm tra nghiệm, gom tuyến và giải MILP trên một CPU logic. Mỗi seed và cả hai nghiệm cuối đều được kiểm tra độc lập. Ngân sách là giới hạn tối đa, nên hybrid có thể kết thúc sớm khi MILP giải xong. Hai nhánh chạy ở hai thời điểm khác nhau.

Hậu xử lý tốn 0.296 giây CPU trên cả 8 instance. Cột `delta_gap_sp_only_pp` trong CSV đo riêng lợi ích MILP trên đúng pool HGS rút ngắn, giúp phân biệt hiệu ứng ghép tuyến với biến động do giới hạn thời gian HGS.

[Số liệu đầy đủ](comparison.csv) · [Baseline](../linux-full/REPORT.md) · [Cấu hình môi trường](environment.txt)
