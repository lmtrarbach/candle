import pytest

from candle.db import Project, count_words


@pytest.fixture
def project(tmp_path):
    p = Project.create(tmp_path / "novel.candle", "My Novel", "Ann Author")
    yield p
    p.close()


def test_create_has_first_chapter_and_scene(project):
    chapters = project.list("chapters")
    assert [c["title"] for c in chapters] == ["Chapter 1"]
    assert len(project.list("scenes", chapter_id=chapters[0]["id"])) == 1
    assert project.title == "My Novel"
    assert project.get_meta("author") == "Ann Author"


def test_create_refuses_existing_file(tmp_path, project):
    with pytest.raises(FileExistsError):
        Project.create(project.path, "Again")


def test_count_words():
    assert count_words("") == 0
    assert count_words("It's a well-known fact, isn't it?") == 6
    assert count_words("Não há café aqui.") == 4


def test_ordering_and_move(project):
    a = project.insert("characters", name="A")
    b = project.insert("characters", name="B")
    c = project.insert("characters", name="C")
    assert [r["id"] for r in project.list("characters")] == [a, b, c]
    assert project.move("characters", c, -1)
    assert [r["id"] for r in project.list("characters")] == [a, c, b]
    assert not project.move("characters", a, -1)


def test_scene_move_between_chapters(project):
    ch1 = project.list("chapters")[0]["id"]
    ch2 = project.insert("chapters", title="Two")
    s = project.insert("scenes", chapter_id=ch1, title="moving")
    project.move_scene_to_chapter(s, ch2)
    assert [r["title"] for r in project.list("scenes", chapter_id=ch2)] == ["moving"]


def test_deleting_entity_removes_links_and_pov(project):
    scene = project.list("scenes")[0]["id"]
    hero = project.insert("characters", name="Hero")
    project.set_link(scene, "character", hero, True)
    project.update("scenes", scene, pov_id=hero)
    project.delete("characters", hero)
    assert project.links(scene, "character") == set()
    assert project.get("scenes", scene)["pov_id"] is None


def test_deleting_chapter_cascades(project):
    ch = project.list("chapters")[0]["id"]
    project.delete("chapters", ch)
    assert project.list("scenes") == []


def test_word_totals_and_today(project):
    project.start_day()
    scene = project.list("scenes")[0]["id"]
    project.save_scene_content(scene, "<p>one two three</p>", "one two three")
    assert project.total_words() == 3
    assert project.words_today() == 3


def test_revisions(project):
    scene = project.list("scenes")[0]["id"]
    project.save_scene_content(scene, "v1", "first draft")
    project.add_revision(scene)
    project.save_scene_content(scene, "v2", "second")
    revs = project.revisions(scene)
    assert len(revs) == 1 and revs[0]["content"] == "v1" and revs[0]["words"] == 2


def test_character_answers(project):
    c = project.insert("characters", name="Hero", role="main")
    project.set_answer(c, "psychology", 0, "brave")
    project.set_answer(c, "psychology", 0, "reckless")
    assert project.answers(c) == {("psychology", 0): "reckless"}


def test_backup_keeps_latest(tmp_path, project):
    folder = tmp_path / "backups"
    for _ in range(3):
        project.backup(folder, keep=2)
    backups = list(folder.glob("*.candle"))
    assert 1 <= len(backups) <= 2
    copy = Project(backups[0])
    assert copy.title == "My Novel"
    copy.close()


def test_bad_identifier_rejected(project):
    with pytest.raises(ValueError):
        project.list("scenes; DROP TABLE scenes")
