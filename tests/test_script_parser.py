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
