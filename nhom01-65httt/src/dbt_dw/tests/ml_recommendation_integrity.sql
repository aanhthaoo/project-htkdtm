{#- Khuyến nghị phải nhất quán: hành động và độ chắc chắn thuộc tập cho phép; hành động khớp dấu điểm (ngưỡng 0,5);
    độ chắc chắn "low" khi giữ nguyên; tuần áp dụng là thứ Hai; lập TRƯỚC khi tuần áp dụng bắt đầu (không nhìn trước tương lai);
    mỗi (ngành, tuần, mô hình) đúng một dòng. Trả về các dòng vi phạm. -#}
select r.sector_key, r.week_start_date_key, r.model_key
from {{ ref('fact_recommendation') }} r
join {{ ref('dim_time') }} t on t.date_key = r.week_start_date_key
where r.action not in ('increase', 'decrease', 'hold')
   or r.confidence not in ('high', 'medium', 'low')
   or (r.action = 'increase' and r.score < 0.5)
   or (r.action = 'decrease' and r.score > -0.5)
   or (r.action = 'hold' and (r.score >= 0.5 or r.score <= -0.5 or r.confidence <> 'low'))
   or r.made_at >= t.date::timestamp
   or t.day_of_week <> 1
union all
select sector_key, week_start_date_key, model_key
from {{ ref('fact_recommendation') }}
group by 1, 2, 3 having count(*) > 1
