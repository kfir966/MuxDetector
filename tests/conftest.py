def pytest_addoption(parser):
    parser.addoption(
        "--show-expected-actual",
        action="store_true",
        help="Print expected and actual results for the end-to-end MUX cases",
    )
