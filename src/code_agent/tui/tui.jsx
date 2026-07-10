#!/usr/bin/env node
// tui.mjs — 最小可工作的 Ink TUI，把每次输入当 prompt 调 agent.py
//
// 跑：npm start        或     node tui.mjs
// 退：Ctrl-C
//
// 关键点（你前几条刚学过的）：
//   - 整个进程里，Ink 只管"画"和"接按键"，
//     真正的 agent loop 在另一个进程跑（agent.py），TUI 是它的"view 层"。
//   - TUI 跟 agent.py 的通信 = 把 prompt 通过命令行参数传过去，
//     把 agent.py 的 stdout 拿回来塞进 React state。
//   - 所有"显示更新"都走同一套路：事件 → setState → React 自动重画。

import React, { useState } from 'react';
import { Box, Text, render, useApp, useInput } from 'ink';
import TextInput from 'ink-text-input';
import { spawn } from 'node:child_process';

// ----------------------------------------------------------------
// 唯一的状态：3 个变量。整个 UI 都是这 3 个的"投影"。
// ----------------------------------------------------------------
function App() {
  const [messages, setMessages] = useState([]);   // 对话历史 [{role, text}, ...]
  const [draft,    setDraft]    = useState('');   // 当前输入框内容
  const [status,   setStatus]   = useState('idle'); // 'idle' | 'thinking'
  const { exit } = useApp();

  // 收到 Ctrl-C 退出
  useInput((_input, key) => {
    if (key.ctrl && _input === 'c') exit();
  });

  // ----------------------------------------------------------------
  // 用户按回车时触发：spawn 一个 agent.py 子进程，等它跑完拿 stdout
  // ----------------------------------------------------------------
  const onSubmit = async (prompt) => {
    if (!prompt.trim() || status === 'thinking') return;

    // 1) 把用户消息推进历史
    setMessages((m) => [...m, { role: 'user', text: prompt }]);
    setDraft('');                            // 清空输入框
    setStatus('thinking');

    // 2) 开一个 agent.py 子进程（这就是"前后端"——只是用 fork/exec 通信）
    let stdout = '', stderr = '';
    try {
      const child = spawn('python3', ['src/code_agent/exec_loop/agent.py', '--quiet', prompt], {
        cwd: process.cwd(),
      });
      child.stdout.on('data', (c) => { stdout += c; });
      child.stderr.on('data', (c) => { stderr += c; });

      const code = await new Promise((resolve) => child.on('close', resolve));
      const reply = code === 0
        ? (stdout.trim() || '(no response)')
        : `[exit ${code}] ${(stderr || stdout).trim()}`;

      // 3) 把 agent 的回复推进历史 → setState 触发 React 重画
      setMessages((m) => [...m, { role: 'assistant', text: reply }]);
    } catch (e) {
      setMessages((m) => [...m, { role: 'assistant', text: `Error: ${e.message}` }]);
    } finally {
      setStatus('idle');
    }
  };

  // ----------------------------------------------------------------
  // render：把 state 画到屏幕。每个 <Box> / <Text> 内部就是拼 ANSI 串。
  // ----------------------------------------------------------------
  return (
    <Box flexDirection="column">

      {/* 上半：历史消息 */}
      <Box
        flexDirection="column"
        flexGrow={1}
        borderStyle="round"
        borderColor="cyan"
        paddingX={1}
      >
        {messages.length === 0 ? (
          <Text dimColor>Ask the agent anything. Ctrl-C to exit.</Text>
        ) : (
          messages.map((m, i) => (
            <Box key={i} flexDirection="column" marginBottom={1}>
              <Text bold color={m.role === 'user' ? 'magenta' : 'cyan'}>
                {m.role === 'user' ? '你 ❯' : 'AI ❯'}
              </Text>
              <Text>{m.text}</Text>
            </Box>
          ))
        )}
      </Box>

      {/* 下半：分隔线 + 状态 + 输入框 */}
      <Box marginTop={1} flexDirection="row">
        <Text color="green" bold>{'❯ '}</Text>
        {status === 'thinking' ? (
          <Text color="yellow">⏵ thinking…</Text>
        ) : (
          <TextInput
            value={draft}
            onChange={setDraft}
            onSubmit={onSubmit}
            placeholder=""
          />
        )}
      </Box>
    </Box>
  );
}

render(<App />);
