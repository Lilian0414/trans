from services.text_parser import parse_lyrics


def test_parser_preserves_internal_blank_lines_and_order():
    lines = parse_lyrics("\n  君の声  \n\n夜を越えて\n\n")
    assert [(line.id, line.text, line.is_blank) for line in lines] == [
        (0, "君の声", False),
        (None, "", True),
        (1, "夜を越えて", False),
    ]


def test_parser_treats_full_width_whitespace_as_a_blank_line():
    lines = parse_lyrics("我は官軍我敵は\n\u3000\u3000\u3000\n天地容れざる朝敵ぞ")
    assert [(line.id, line.text, line.is_blank) for line in lines] == [
        (0, "我は官軍我敵は", False),
        (None, "", True),
        (1, "天地容れざる朝敵ぞ", False),
    ]
