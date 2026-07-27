#!/usr/bin/env node
// tui.jsx — Ink TUI 前端，spawn agent.py 一次，IPC 多次。
//
// 跑：npm start        或     node tui.jsx
// 退：Ctrl-C（同时杀 agent）
//
// 协议（与 agent.py REPL）：
//   stdin : 每行一个 prompt
//   stdout: 第一行 "READY"，之后每段回复以 "=== END ===" 行结束
//   stderr: agent verbose 日志（TUI 直接打到终端 stderr，不进 TUI 屏）

import React, { useState, useEffect, useRef } from 'react';
import { Box, Text, render, useApp, useInput } from 'ink';
import TextInput from 'ink-text-input';
import { spawn } from 'node:child_process';

const END_SENTINEL = '=== END ===';

function App() {
  const [messages, setMessages] = useState([]);   // 对话历史 [{role, text}, ...]
  const [draft,    setDraft]    = useState('');   // 当前输入框内容
  const [status,   setStatus]   = useState('idle'); // 'idle' | 'thinking'
  const { exit } = useApp();

  // 用 ref 存 agent 进程和"等当前回复"的 promise resolver
  // —— ref 改不改都不触发重渲染
  const childRef    = useRef(null);
  const resolveRef  = useRef(null);
  const readyResolveRef = useRef(null);

  // Ctrl-C 退出
  useInput((_input, key) => {
    if (key.ctrl && _input === 'c') exit();
  });

  // ------------------------------------------------------------
  // App 挂载时启动 agent（一次），卸载时 kill
  // ------------------------------------------------------------
  useEffect(() => {
    const child = spawn('python3', ['src/code_agent/exec_loop/agent.py', '--quiet'], {
      cwd: process.cwd(),
    });
    childRef.current = child;

    // 行级 buffer：按行处理 stdout
    let stdoutBuf = '';
    let readySeen = false;
    let replyBuf  = '';

    function processLine(line) {
      // 第一行必须是 READY（启动握手）
      if (!readySeen) {
        if (line === 'READY') {
          readySeen = true;
          if (readyResolveRef.current) {
            readyResolveRef.current();
            readyResolveRef.current = null;
          }
        }
        return;
      }

      // END 哨兵 = 回复结束
      if (line === END_SENTINEL) {
        if (resolveRef.current) {
          resolveRef.current(replyBuf.replace(/\n$/, ''));
          replyBuf = '';
          resolveRef.current = null;
        }
        return;
      }

      // 普通行 = 累积到当前回复
      replyBuf += line + '\n';
    }

    child.stdout.on('data', (chunk) => {
      stdoutBuf += chunk.toString('utf8');
      let nl;
      while ((nl = stdoutBuf.indexOf('\n')) >= 0) {
        const line = stdoutBuf.slice(0, nl);
        stdoutBuf = stdoutBuf.slice(nl + 1);
        processLine(line);
      }
    });

    // agent 的 verbose 日志直接打到 TUI 的 stderr（终端可见，Ink 屏幕外）
    child.stderr.on('data', (c) => process.stderr.write(c));

    // 进程死了：未 resolve 的 submit 收尸
    child.on('exit', (code) => {
      if (resolveRef.current) {
        resolveRef.current(`[agent exited with code ${code}]`);
        resolveRef.current = null;
      }
      if (!readySeen && readyResolveRef.current) {
        readyResolveRef.current();
        readyResolveRef.current = null;
      }
    });

    // App 卸载 → 杀 agent
    return () => {
      try { child.kill('SIGTERM'); } catch (_) {}
    };
  }, []);

  // ------------------------------------------------------------
  // 用户按回车：写 prompt 到 agent stdin，等 END 后拿回复
  // ------------------------------------------------------------
  const onSubmit = async (prompt) => {
    if (!prompt.trim() || status === 'thinking') return;

    setMessages((m) => [...m, { role: 'user', text: prompt }]);
    setDraft('');
    setStatus('thinking');

    // 等 agent 回复（END 哨兵触发 resolve；进程死了也会 resolve）
    const reply = await new Promise((resolve) => {
      resolveRef.current = resolve;
      childRef.current.stdin.write(prompt + '\n');
    });

    setMessages((m) => [...m, { role: 'assistant', text: reply || '(no response)' }]);
    setStatus('idle');
  };

  // ------------------------------------------------------------
  // render：把 state 画到屏幕
  // ------------------------------------------------------------
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
