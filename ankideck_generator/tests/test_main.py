from ankideck_generator.main import build_arg_parser


def test_arg_parser_resume_defaults_to_false() -> None:
    parser = build_arg_parser()
    args = parser.parse_args([])
    assert args.resume is False


def test_arg_parser_resume_opt_in() -> None:
    parser = build_arg_parser()
    args = parser.parse_args(["--resume"])
    assert args.resume is True


def test_arg_parser_no_resume_overrides_resume() -> None:
    parser = build_arg_parser()
    args = parser.parse_args(["--resume", "--no-resume"])
    assert args.resume is False
