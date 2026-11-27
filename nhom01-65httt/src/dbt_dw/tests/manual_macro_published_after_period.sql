{#- Số liệu vĩ mô nhập tay phải được công bố SAU khi kỳ kết thúc (nếu không mô hình sẽ nhìn trước tương lai); ngày công bố không ở tương lai.
    Trả về các dòng vi phạm. -#}
select indicator_key, date_key, period_end_date_key, published_date_key
from {{ ref('fact_macro_indicator') }}
where source = 'manual_csv'
  and (published_date_key < period_end_date_key or published_date_key > {{ date_key('current_date') }})
