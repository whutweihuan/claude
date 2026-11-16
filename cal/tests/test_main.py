def test_main_entry_point():
    import main

    # main.py must expose a callable entry point that opens the window so a
    # real user can run `python main.py` and actually use the calculator.
    assert callable(main.main)
