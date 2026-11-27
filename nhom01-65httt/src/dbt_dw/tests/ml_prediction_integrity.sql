{#- Dự báo phải nhất quán: xác suất trong [0, 1]; lớp dự báo khớp xác suất (>= 0,5 là INFLOW); chân trời 1 tuần;
    dự báo đã có giá trị thực thì lớp thực khớp dấu giá trị thực; dự báo được lập TRƯỚC khi tuần mục tiêu bắt đầu
    (không nhìn trước tương lai); tuần mục tiêu là thứ Hai. Trả về các dòng vi phạm. -#}
select p.*
from {{ ref('fact_prediction') }} p
join {{ ref('dim_time') }} t on t.date_key = p.target_week_start_date_key
where p.prob_inflow < 0 or p.prob_inflow > 1
   or (p.prob_inflow >= 0.5) <> (p.predicted_class = 'INFLOW')
   or p.horizon_weeks <> 1
   or (p.actual_net_value_bn is not null and (p.actual_net_value_bn > 0) <> (p.actual_class = 'INFLOW'))
   or p.made_at >= t.date::timestamp
   or t.day_of_week <> 1
