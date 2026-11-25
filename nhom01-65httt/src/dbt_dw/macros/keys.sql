{#- Khóa thay thế ổn định (không đổi khi thêm dòng mới): 60 bit đầu của md5 -> bigint. -#}
{% macro surrogate_key(expr) -%}
    (('x' || substr(md5(({{ expr }})::text), 1, 15))::bit(60)::bigint)
{%- endmacro %}

{#- date_key = YYYYMMDD dạng số nguyên -#}
{% macro date_key(expr) -%}
    (to_char({{ expr }}, 'YYYYMMDD'))::int
{%- endmacro %}
