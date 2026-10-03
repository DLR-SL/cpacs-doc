"""The entry point of the Windows executable.

It is started three ways — by double click, by dropping a schema on it, from a
terminal — and only the last one comes with a subcommand. The tests record the
command line the launcher hands to the CLI, which is the whole of its job.
"""

from cpacs_doc import launch


class Recorder:
    def __init__(self, code=0, choice=None):
        self.code = code
        self.choice = choice
        self.calls = []
        self.asked = 0
        self.paused = 0

    def run(self, argv):
        self.calls.append(argv)
        return self.code

    def choose(self):
        self.asked += 1
        return self.choice

    def pause(self):
        self.paused += 1

    def launch(self, argv):
        return launch.main(argv, run=self.run, choose=self.choose, pause=self.pause)


def test_a_schema_dropped_on_the_executable_is_served_and_opened():
    recorder = Recorder()
    assert recorder.launch(["C:/work/cpacs_schema.xsd"]) == 0
    assert recorder.calls == [["serve", "C:/work/cpacs_schema.xsd", "--open"]]


def test_a_subcommand_is_passed_through_unchanged():
    recorder = Recorder()
    recorder.launch(["report", "schema.xsd", "--limit", "0"])
    assert recorder.calls == [["report", "schema.xsd", "--limit", "0"]]


def test_an_option_alone_is_passed_through_unchanged():
    recorder = Recorder()
    recorder.launch(["--version"])
    assert recorder.calls == [["--version"]]


def test_a_double_click_asks_for_the_schema():
    recorder = Recorder(choice="D:/cpacs/schema/cpacs_schema.xsd")
    assert recorder.launch([]) == 0
    assert recorder.asked == 1
    assert recorder.calls == [["serve", "D:/cpacs/schema/cpacs_schema.xsd", "--open"]]


def test_a_cancelled_dialog_ends_quietly():
    recorder = Recorder(choice=None)
    assert recorder.launch([]) == 0
    assert recorder.calls == []


def test_a_failure_keeps_the_window_open_long_enough_to_be_read():
    """A console started by double click closes with the process, and the
    reason it stopped would go with it."""
    recorder = Recorder(code=2)
    assert recorder.launch(["broken.xsd"]) == 2
    assert recorder.paused == 1


def test_a_subcommand_never_waits():
    """From a terminal the output stays where it is; a prompt would only block
    a script."""
    recorder = Recorder(code=1)
    assert recorder.launch(["report", "schema.xsd"]) == 1
    assert recorder.paused == 0


def test_success_does_not_wait():
    recorder = Recorder(code=0)
    recorder.launch(["schema.xsd"])
    assert recorder.paused == 0
