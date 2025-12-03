MOD_INFO = {
    "id": "testpatch",
    "name": "Test PatchMe",
    "description": "",
    "version": "0.0.1",
    "dependencies": ["modcore"],
    "enabled": False
}

from modcore import hook
from hlmod import get_obj_field, Hook, assert_code_sha, get_global
from typing import Optional
from stubs import TestClass, SuperTestClass

def initialize():
    # Haxe 4.3.6 Windows
    # assert_code_sha("c5b81c94db4a9de0e78e8779adabddf6b4246fd1fc938307306c27271e2df826")
    # haxe 4.3.6 Linux
    # assert_code_sha("52ac527751d7aa20d1be9024de88628f389336dbed3d915d82f55cabf58c3617")
    pass

@hook("TestClass.do_a_thing")
def hook_do_a_thing(self: Hook, this: TestClass):
    self.call_original(this)
    print("Hooked do a thing!!")

@hook("$PatchMe.thing")
def thing(self: Hook, val: float, val2: Optional[float], msg: str, val3: Optional[TestClass]):
    print("Hook!")
    val = 2.0
    val2 = 1.0
    msg = "Hello, hlmod world!"
    assert val3 is not None
    val3.do_a_thing()
    print(val3.test)
    #print(SuperTestClass.STATIC_VAL)
    # s_supertestclass: S_SuperTestClass = get_global(23)
    # print(s_supertestclass)
    # print(s_supertestclass.STATIC_VAL)
    self.call_original(val, 2.0, msg, val3)

@hook("$PatchMe.main")
def hook_main(self: Hook):
    self.call_original()
    print("Called and hooked main!!")
    
@hook("$PatchMe.closure_test_2")
def closure_test_2(self: Hook, closure):
    print(closure)
    self.call_original(closure)