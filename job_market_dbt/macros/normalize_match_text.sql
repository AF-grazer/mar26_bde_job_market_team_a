{% macro normalize_match_text(expression) -%}
nullif(
    trim(
        regexp_replace(
            regexp_replace(
                lower(
                    translate(
                        coalesce({{ expression }}, ''),
                        'àâäáãåçèéêëìíîïñòóôöõùúûüýÿ',
                        'aaaaaaceeeeiiiinooooouuuuyy'
                    )
                ),
                '[^a-z0-9]+',
                ' ',
                'g'
            ),
            '\s+',
            ' ',
            'g'
        )
    ),
    ''
)
{%- endmacro %}

{% macro normalize_title_match(expression) -%}
nullif(
    trim(
        regexp_replace(
            regexp_replace(
                regexp_replace(
                    coalesce({{ normalize_match_text(expression) }}, ''),
                    '\b(h f|f h|hf)\b',
                    '',
                    'g'
                ),
                '\b(h|f)\b',
                '',
                'g'
            ),
            '\s+',
            ' ',
            'g'
        )
    ),
    ''
)
{%- endmacro %}

{% macro normalize_company_match(expression) -%}
nullif(
    trim(
        regexp_replace(
            regexp_replace(
                regexp_replace(
                    regexp_replace(
                        coalesce({{ normalize_match_text(expression) }}, ''),
                        '\b(sas|sasu|sarl|sa|eurl|cfa|groupe|group|france)\b',
                        '',
                        'g'
                    ),
                    '\b(emploi|interim|interimaire|interimaires|staffing|recrutement)\b',
                    '',
                    'g'
                ),
                '[0-9]+',
                '',
                'g'
            ),
            '\s+',
            ' ',
            'g'
        )
    ),
    ''
)
{%- endmacro %}

{% macro normalize_city_match(expression) -%}
nullif(
    trim(
        regexp_replace(
            regexp_replace(
                regexp_replace(
                    regexp_replace(
                        regexp_replace(
                            regexp_replace(
                                coalesce({{ normalize_match_text(expression) }}, ''),
                                '(^[0-9]{5}\s+)|((\s+)?\(?[0-9]{2,5}\)?)$',
                                '',
                                'g'
                            ),
                            '\bteletravail\b|\bpartiel\b|\bremote\b|\bhybride\b',
                            '',
                            'g'
                        ),
                        '\b[0-9]{1,2}e\b',
                        '',
                        'g'
                    ),
                    '\b[0-9]{1,5}\b',
                    '',
                    'g'
                ),
                '\b(a|au|aux)\b',
                '',
                'g'
            ),
            '\s+',
            ' ',
            'g'
        )
    ),
    ''
)
{%- endmacro %}
