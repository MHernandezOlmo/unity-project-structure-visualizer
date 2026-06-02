from parser.script_parser import parse_script


PLAYER_CS = """\
using UnityEngine;
using System.Collections;

public class PlayerController : MonoBehaviour
{
    [SerializeField]
    private float moveSpeed = 5f;

    [SerializeField]
    private Rigidbody rb;

    [SerializeField] private AudioClip jumpSound;

    void Update() {}
}
"""

ENEMY_CS = """\
using UnityEngine;
using System.Collections.Generic;

public class EnemyAI : BaseEnemy, IAttackable, IDamageable
{
    [SerializeField]
    private List<Transform> patrolPoints;

    [SerializeField, HideInInspector]
    private float aggroRange = 10f;
}
"""

INTERFACE_CS = """\
using UnityEngine;

public interface IDamageable
{
    void TakeDamage(float amount);
}
"""

NO_CLASS_CS = """\
// Just a comment file
using UnityEngine;
"""


def test_class_name_and_base():
    info = parse_script("PlayerController.cs", PLAYER_CS)
    assert info.class_name == "PlayerController"
    assert info.base_class == "MonoBehaviour"
    assert info.interfaces == []


def test_usings():
    info = parse_script("PlayerController.cs", PLAYER_CS)
    assert "UnityEngine" in info.usings
    assert "System.Collections" in info.usings


def test_serialize_fields_newline_syntax():
    info = parse_script("PlayerController.cs", PLAYER_CS)
    names = [f["name"] for f in info.serialize_fields]
    assert "moveSpeed" in names
    assert "rb" in names


def test_serialize_field_inline_syntax():
    info = parse_script("PlayerController.cs", PLAYER_CS)
    names = [f["name"] for f in info.serialize_fields]
    assert "jumpSound" in names


def test_multiple_interfaces():
    info = parse_script("EnemyAI.cs", ENEMY_CS)
    assert info.class_name == "EnemyAI"
    assert info.base_class == "BaseEnemy"
    assert "IAttackable" in info.interfaces
    assert "IDamageable" in info.interfaces


def test_generic_serialize_field():
    info = parse_script("EnemyAI.cs", ENEMY_CS)
    field = next(f for f in info.serialize_fields if f["name"] == "patrolPoints")
    assert "List" in field["type"]


def test_stacked_attribute():
    info = parse_script("EnemyAI.cs", ENEMY_CS)
    names = [f["name"] for f in info.serialize_fields]
    assert "aggroRange" in names


def test_interface_no_class():
    info = parse_script("IDamageable.cs", INTERFACE_CS)
    assert info.class_name is None or info.class_name == "IDamageable"


def test_no_class():
    info = parse_script("empty.cs", NO_CLASS_CS)
    assert info.class_name is None
    assert info.serialize_fields == []


# --- Regression tests for code-review bugs ---

GENERIC_BASE_CS = """\
using UnityEngine;

public class SaveSystem : SerializableDictionary<string, int>
{
    [SerializeField]
    private float saveInterval = 5f;
}
"""

BLANK_LINE_SERIALIZE_CS = """\
using UnityEngine;

public class Foo : MonoBehaviour
{
    [SerializeField]

    private float speed;

    [SerializeField]

    private GameObject target;
}
"""

COMMENT_SERIALIZE_CS = """\
using UnityEngine;

public class Foo : MonoBehaviour
{
    [SerializeField]
    // movement speed in units/sec
    private float speed;
}
"""


def test_generic_base_class_not_split_on_comma():
    info = parse_script("SaveSystem.cs", GENERIC_BASE_CS)
    assert info.base_class == "SerializableDictionary<string, int>"
    assert info.interfaces == []


def test_serialize_field_blank_line_between_attribute_and_field():
    info = parse_script("Foo.cs", BLANK_LINE_SERIALIZE_CS)
    names = [f["name"] for f in info.serialize_fields]
    assert "speed" in names
    assert "target" in names
    types = {f["name"]: f["type"] for f in info.serialize_fields}
    assert types["speed"] == "float"
    assert types["target"] == "GameObject"


def test_serialize_field_comment_between_attribute_and_field():
    info = parse_script("Foo.cs", COMMENT_SERIALIZE_CS)
    names = [f["name"] for f in info.serialize_fields]
    assert "speed" in names
    assert info.serialize_fields[0]["type"] == "float"


# --- References detection tests ---

INSTALLER_CS = """\
using UnityEngine;

public class Installer : MonoBehaviour
{
    private PlayerController _player;
    private EnemySpawner _spawner;

    void Start()
    {
        _player = new PlayerController();
        _spawner = GetComponent<EnemySpawner>();
        var gm = FindObjectOfType<GameManager>();
    }
}
"""


def test_references_new_instance():
    info = parse_script("Installer.cs", INSTALLER_CS)
    assert "PlayerController" in info.references


def test_references_get_component():
    info = parse_script("Installer.cs", INSTALLER_CS)
    assert "EnemySpawner" in info.references


def test_references_find_object_of_type():
    info = parse_script("Installer.cs", INSTALLER_CS)
    assert "GameManager" in info.references


def test_references_typed_field():
    info = parse_script("Installer.cs", INSTALLER_CS)
    # EnemySpawner appears in both the typed field and GetComponent<> — should be deduplicated
    assert info.references.count("EnemySpawner") == 1


def test_references_excludes_own_class():
    info = parse_script("Installer.cs", INSTALLER_CS)
    assert "Installer" not in info.references


def test_references_empty_when_no_deps():
    info = parse_script("PlayerController.cs", PLAYER_CS)
    # PlayerController has no references to other project scripts
    assert "PlayerController" not in info.references
