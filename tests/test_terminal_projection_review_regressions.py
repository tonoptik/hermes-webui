"""Regression probes for the concrete review findings on upstream PR #8496."""
import ast
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from tests.js_source_extract import extract_function


def node(script):
    executable = shutil.which('node')
    if not executable:
        pytest.skip('node required')
    result = subprocess.run([executable, '-'], input=script, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr


def test_legacy_complete_terminal_snapshot_preserves_authoritative_answer():
    helper = extract_function(Path('static/messages.js').read_text(encoding='utf-8'), '_applyEmbeddedTerminalSession')
    node(f"""
const assert=require('node:assert/strict');
const apply=eval('('+{json.dumps(helper)}+')');
const current={{session_id:'s',message_count:2}};
const rows=[{{id:1,role:'user',content:'q'}},{{id:2,role:'assistant',content:'streamed'}}];
const saved=[rows[0],{{...rows[1],content:'Saved transformed answer'}}];
const incoming={{session_id:'s',messages:saved,message_count:2}};
assert.equal(apply(incoming,current,rows,0).messages[1].content,'Saved transformed answer');
assert.equal(incoming._messages_offset,undefined);
assert.equal(apply({{...incoming,message_count:3}},current,rows,0),null);
assert.equal(apply({{...incoming,_messages_truncated:true}},current,rows,0),null);
""")


def test_busy_paging_rebases_saved_cards_from_both_pages_without_touching_live():
    source=Path('static/sessions.js').read_text(encoding='utf-8')
    merge=extract_function(source, '_mergePagedToolCalls')
    sync=extract_function(source, '_syncToolCallsForLoadedMessages')
    node(f"""
const assert=require('node:assert/strict');
const merge=eval('('+{json.dumps(merge)}+')');
const S={{busy:true,activeStreamId:'run',session:{{tool_calls:[{{id:'later',assistant_msg_idx:21}}]}},toolCalls:[{{id:'live'}}]}};
const sync=eval('('+{json.dumps(sync)}+')');
const live=S.toolCalls;
const cards=merge(S.session.tool_calls,[{{id:'earlier',assistant_msg_idx:1}}],130,100);
sync([],cards);
assert.equal(S.session.tool_calls.find(c=>c.id==='later').assistant_msg_idx,51);
assert.equal(S.session.tool_calls.find(c=>c.id==='earlier').assistant_msg_idx,1);
assert.equal(S.toolCalls,live);
assert.equal(S.toolCalls[0].id,'live');
""")


def test_gateway_retained_checkpoint_row_receives_stable_id():
    tree=ast.parse(Path('api/gateway_chat.py').read_text(encoding='utf-8'))
    branches=[n for n in ast.walk(tree) if isinstance(n,ast.If) and ast.unparse(n.test)=='len(current_display_rows) == 1']
    assert len(branches)==1
    checkpoint={'role':'user','content':'q'}
    scope={'current_display_rows':[checkpoint], 'user_msg':{'timestamp':12,'id':151}}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[branches[0]],type_ignores=[])), '<gateway-checkpoint>', 'exec'), scope)
    assert checkpoint['id']==151
    checkpoint['id']=99
    exec(compile(ast.fix_missing_locations(ast.Module(body=[branches[0]],type_ignores=[])), '<gateway-checkpoint>', 'exec'), scope)
    assert checkpoint['id']==99
