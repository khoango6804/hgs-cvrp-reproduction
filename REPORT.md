# Báo cáo tái lập HGS-CVRP

**Nên giữ paper này cho final project.** Mã C++ công khai của Vidal đã chạy được trên X-set. Cả 80 nghiệm trong pilot đều qua kiểm tra độc lập. Hai instance nhỏ đạt best-known solution (BKS) ở ít nhất một seed. Với 1.000 khách, khoảng cách đến BKS còn lớn ở ngân sách 24 giây, nên thời lượng chạy là biến cần kiểm soát khi so sánh chất lượng nghiệm.

Paper *Hybrid Genetic Search for the CVRP: Open-Source Implementation and SWAP\* Neighborhood* của Thibaut Vidal xuất bản trong *Computers & Operations Research*, tập 140, bài 105643, năm 2022. Tạp chí này có trong danh sách môn học. [Bài báo](https://doi.org/10.1016/j.cor.2021.105643) · [Bản arXiv đầy đủ](https://arxiv.org/html/2012.10384) · [Yêu cầu môn học](<Paper presentation requirement.pdf>)

## Bài toán và thuật toán

CVRP tối thiểu hóa tổng quãng đường của các tuyến. Mỗi tuyến xuất phát từ depot và quay về depot, tổng nhu cầu trên tuyến không vượt tải trọng xe, và mỗi khách được phục vụ đúng một lần. Với X-set, tên `k` biểu thị cận dưới số tuyến. Solver dùng cận trên nội bộ mặc định của tác giả. Chẳng hạn nghiệm BKS trên `X-n101-k25` có 26 tuyến.

HGS dùng Ordered Crossover trên hoán vị khách, Split để tách tuyến và local search với Relocate, Swap, 2-Opt, 2-Opt* và SWAP*. SWAP* trao đổi hai khách ở hai tuyến và cho phép chọn lại vị trí chèn trong từng tuyến. HGS duy trì hai quần thể khả thi và không khả thi, dùng broken-pairs distance để quản lý đa dạng và điều chỉnh penalty theo tỷ lệ nghiệm khả thi. [Mô tả thuật toán](https://arxiv.org/html/2012.10384#S2)

## Thiết lập tái lập

- Biên dịch mã C++ từ tag `v1.0.0`, commit `35b32d8e9552074f52444d51ea1fe8aec9055467`. Cả 16 file trong `Program` khớp từng byte với archive phát hành. Tác giả mô tả tag này là bản gắn với paper và có một bản vá nhỏ cho cận kích thước đội xe, repair trong local search và khoảng giá trị penalty. [Release v1.0.0](https://github.com/vidalt/HGS-CVRP/releases/tag/v1.0.0) · [Commit bản vá](https://github.com/vidalt/HGS-CVRP/commit/35b32d8e9552074f52444d51ea1fe8aec9055467)
- Giữ mặc định `μ=25`, `λ=40`, `nElite=4`, `nClosest=5`, `Γ=20` và tỷ lệ khả thi mục tiêu `0,2`. Với `-it 20000` và `-t`, HGS khởi động lại quần thể khi chạm ngưỡng không cải thiện và giữ nghiệm tốt nhất đến hết thời gian. [Bảng 1 và thiết lập benchmark](https://arxiv.org/html/2012.10384#S4)
- Dữ liệu gồm 100 file X đi kèm release. Nội dung sau khi chuẩn hóa khoảng trắng khớp 100/100 file với archive của CVRPLIB. Pilot chọn tám instance theo kích thước, chạy seed 1–10, năm tiến trình đồng thời. Mỗi run dùng một luồng. `-t` bằng `ceil(0,01 × 2,4 × số khách)`, vì CLI nhận số giây nguyên. [CVRPLIB](https://galgos.inf.puc-rio.br/cvrplib/index.php/en/cvrp/instances)
- Môi trường pilot dùng Windows 11 26H2, Core i5-12400F và GCC 16.2.0. `clock()` của CRT Windows đo thời gian thực đã trôi qua. Paper dùng thời gian CPU trên CentOS 7.8, Xeon Gold 6148 và g++ 9.1.0. CRT, compiler, phần cứng và tải đồng thời có thể thay đổi số vòng lặp hoàn thành cũng như quỹ đạo tìm kiếm. [Microsoft CRT](https://learn.microsoft.com/en-us/cpp/c-runtime-library/reference/clock?view=vs-2019) · [Môi trường của paper](https://arxiv.org/html/2012.10384#S5)
- Verifier Python xác nhận mỗi khách xuất hiện đúng một lần, từng tuyến tuân thủ tải trọng, và tổng chi phí khớp `.sol` khi cộng `EUC_2D` làm tròn từng cạnh kể cả lượt đi và về depot. Kiểm thử verifier bằng nghiệm bị chèn depot, cost khai sai và tải vượt ngưỡng đều bị từ chối. BKS lịch sử được dùng riêng để chấm `gap = 100 × (cost − BKS) / BKS` theo mốc của paper. [BKS lịch sử](paper_reference.csv)

## Kết quả pilot

| Instance | Giây mỗi seed | BKS năm 2020 | Cost tốt nhất | Gap TB | Gap TB paper ở 100% thời gian | Seed đạt BKS |
|---|---:|---:|---:|---:|---:|---:|
| X-n101-k25 | 3 | 27.591 | 27.591 | 0,000% | 0,00% | 10/10 |
| X-n157-k13 | 4 | 16.876 | 16.876 | 0,025% | 0,00% | 5/10 |
| X-n251-k28 | 6 | 38.684 | 38.899 | 0,821% | 0,02% | 0/10 |
| X-n401-k29 | 10 | 66.163 | 66.767 | 1,073% | 0,14% | 0/10 |
| X-n502-k39 | 13 | 69.226 | 69.479 | 0,421% | 0,02% | 0/10 |
| X-n627-k43 | 16 | 62.164 | 63.415 | 2,204% | 0,33% | 0/10 |
| X-n801-k40 | 20 | 73.305 | 74.748 | 2,223% | 0,27% | 0/10 |
| X-n1001-k43 | 24 | 72.359 | 75.546 | 4,655% | 0,54% | 0/10 |

Gap trung bình của 80 lượt là **1,428%**. Trung bình tám giá trị gap đã làm tròn trong paper là **0,165%** trên cùng tám instance ở đủ ngân sách. Trên toàn bộ 100 instance, paper báo **0,11%** và **44/100 instance đạt BKS** khi lấy nghiệm tốt nhất qua 10 seed. Kết quả ở đây xác nhận khả năng chạy và chất lượng ban đầu của bản phát hành. Phép tái lập đầy đủ cần 1.000 lượt chạy, tương đương khoảng 275 giờ chạy nối tiếp theo ngân sách của paper. [Kết quả từng seed](results/pilot/runs.csv) · [Thống kê theo instance](results/pilot/summary.csv) · [Bảng kết quả gốc](https://arxiv.org/html/2012.10384#S5)

## Ảnh hưởng của ngân sách trên instance lớn

Chạy lại hai instance lớn với cùng seed 1–3, dùng 5% ngân sách paper và sáu tiến trình đồng thời. Cả sáu nghiệm đều qua kiểm tra. Gap giảm ở cả sáu cặp instance và seed.

| Instance | Thời gian ngắn → dài | Gap TB của cùng ba seed | Cost tốt nhất ở 5% |
|---|---:|---:|---:|
| X-n801-k40 | 20 → 96 giây | 2,348% → 1,771% | 74.561 |
| X-n1001-k43 | 24 → 120 giây | 4,630% → 2,899% | 74.310 |

Mức giảm quan sát được là 0,58 và 1,73 điểm phần trăm. Hai đợt có số tiến trình khác nhau và chạy chồng lên nhau trong một khoảng thời gian, nên độ lớn của cải thiện còn phụ thuộc tải máy. Bước tiếp theo ưu tiên chạy đủ ngân sách trên tám instance với 10 seed, cùng môi trường Linux và so sánh theo đúng mốc BKS lịch sử. Chi phí khoảng 25,6 giờ CPU theo thiết lập paper. Kỳ vọng gap giảm rõ ở các instance lớn, nhưng mức giảm quan sát ở 5% chưa đủ để dự đoán điểm cuối. [Kết quả chạy dài hơn](results/extended/runs.csv)

## Thí nghiệm mở rộng cho final project

Ưu tiên ablation SWAP* trên cùng mã nguồn. Giữ seed, ngân sách CPU và cấu hình giống nhau, rồi báo chênh lệch mean gap theo cặp, tỷ lệ đạt BKS và đường hội tụ. Kỳ vọng bản có SWAP* giảm gap rõ hơn ở nhóm tuyến ngắn. Mức chênh tham chiếu giữa HGS-CVRP và HGS-2012 trong paper là 0,10 điểm phần trăm trên 100 instance. So sánh hai bản đó chỉ là mốc tham chiếu vì paper cũng thay đổi cách triển khai HGS và tham số elite. Ablation nhân đôi chi phí của nhóm instance được chọn và cần tránh hiệu ứng sàn trên các instance đã đạt BKS. [Phân tích SWAP* trong paper](https://arxiv.org/html/2012.10384#S5)

## Chạy lại

`genvrp.exe` đã được biên dịch cho Windows x64. Runner cần Python 3.9+ và dùng thư viện chuẩn. Chạy từ thư mục dự án bằng PowerShell.

```powershell
# Pilot theo cấu hình đã chạy
python reproduce.py --jobs 5 --output results/pilot-repeat

# Hai instance lớn, ba seed trùng với pilot
python reproduce.py --instances X-n801-k40 X-n1001-k43 --seeds 1 2 3 `
  --time-fraction 0.05 --jobs 6 --output results/extended-repeat

# Toàn bộ X-set, đủ ngân sách cho mỗi instance
python reproduce.py --instances all --time-fraction 1 --jobs 1 --output results/full
```

Build lại trên Windows với MinGW `g++` trong `PATH`.

```powershell
$sources = (Get-ChildItem 'HGS-CVRP-1.0.0/Program/*.cpp').FullName
g++ -O3 -Wall -std=c++11 -static @sources -o genvrp.exe
```

Trên Linux, có thể chạy `make -C HGS-CVRP-1.0.0/Program` và truyền `--solver HGS-CVRP-1.0.0/Program/genvrp` cho runner. Mỗi lần benchmark lưu `.sol`, log và đường hội tụ `*.sol.PG.csv` theo seed trong thư mục `trials`.
