"use client";

import * as React from "react";
import Link from "next/link";
import { PageTitle } from "@/components/common/PageTitle";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/common/EmptyState";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useAppSelector } from "@/store/hooks";

function Section({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-20">
      <h2 className="text-lg font-semibold mb-3">{title}</h2>
      <Card>
        <CardContent className="pt-6 flex flex-col gap-4 text-sm leading-relaxed">
          {children}
        </CardContent>
      </Card>
    </section>
  );
}

function StepCard({
  n,
  title,
  children,
}: {
  n: number;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-border p-4 flex gap-3">
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground text-sm font-semibold">
        {n}
      </div>
      <div className="flex-1 min-w-0">
        <div className="font-medium mb-1">{title}</div>
        <div className="text-sm text-muted-foreground">{children}</div>
      </div>
    </div>
  );
}

function PageLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="font-medium underline underline-offset-2 decoration-dotted hover:text-foreground"
    >
      {children}
    </Link>
  );
}

interface IntakeRow {
  field: string;
  required: boolean;
  note: string;
}

const INTAKE_FIELDS: IntakeRow[] = [
  { field: "姓名", required: true, note: "建立使用者帳號用" },
  { field: "公司 Email", required: true, note: "必須是 @df-recycle.com / @df-recycle.com.tw" },
  { field: "員工編號", required: false, note: "需與 HR 對帳時帶上" },
  { field: "所屬部門", required: true, note: "決定能用哪一把 SDK Key" },
  { field: "用途 / 專案名稱", required: true, note: "用來對應或建立專案" },
  { field: "需要的模型", required: true, note: "確認是否已在白名單" },
  { field: "預期呼叫量", required: false, note: "用來決定分級或 RPM 限制" },
];

export default function AdminGuidePage() {
  const role = useAppSelector((s) => s.auth.actor?.role);

  if (role !== "admin") {
    return (
      <>
        <PageTitle title="管理者使用說明" />
        <Card>
          <CardContent className="pt-6">
            <EmptyState title="權限不足" description="本頁僅限 admin 存取" />
          </CardContent>
        </Card>
      </>
    );
  }

  return (
    <>
      <PageTitle
        title="管理者使用說明"
        description="向使用者收集什麼、在後台怎麼建立、怎麼交付憑證"
      />

      <div className="flex flex-col gap-8">
        <Section id="overview" title="概述">
          <p>
            管理者是平台憑證、模型白名單、用量稽核的單一窗口。一般使用者<strong>不需登入此網站</strong>，只用 admin 發放的三組憑證在自己的程式碼裡呼叫代理端點。
          </p>
          <p>admin 每次的工作就是兩件：</p>
          <ol className="list-decimal pl-5 space-y-1">
            <li>向使用者收齊資訊</li>
            <li>依序建好 部門 → 專案 → 使用者 → User Token，再一次性交付 SDK Key + User Token + Project Code 三組值</li>
          </ol>
          <p className="text-muted-foreground">
            呼叫端規格（端點、Header、Request/Response、錯誤碼）見「使用者使用說明」，本頁只談後台動作。
          </p>
        </Section>

        <Section id="concepts" title="四個關鍵物件">
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-xl border border-border p-4">
              <Badge>部門</Badge>
              <p className="text-sm mt-2">
                所有東西的容器。SDK Key、專案、使用者都隸屬部門，呼叫時三者必須同部門。
              </p>
            </div>
            <div className="rounded-xl border border-border p-4">
              <Badge>SDK Key</Badge>
              <p className="text-sm mt-2">
                部門層級的程式呼叫憑證（Header <code className="font-mono">X-SDK-Key</code>）。同部門可有多把。
              </p>
            </div>
            <div className="rounded-xl border border-border p-4">
              <Badge>User Token</Badge>
              <p className="text-sm mt-2">
                個人層級的呼叫者身份（Header <code className="font-mono">X-User-Token</code>）。改姓名 / Email / 員編 / 部門會自動失效。
              </p>
            </div>
            <div className="rounded-xl border border-border p-4">
              <Badge>專案</Badge>
              <p className="text-sm mt-2">
                用量歸戶單位（Header <code className="font-mono">X-Project-Code</code>）。同部門可多個專案。
              </p>
            </div>
          </div>
        </Section>

        <Section id="prerequisites" title="平台首次上線（僅做一次）">
          <div className="flex flex-col gap-3">
            <StepCard n={1} title="加入 OpenRouter Key">
              至 <PageLink href="/openrouter-keys">OpenRouter Keys</PageLink> 貼入公司向 OpenRouter 申請的 API Key 並綁部門。明文僅建立時可見一次。
            </StepCard>
            <StepCard n={2} title="同步模型清單">
              至 <PageLink href="/admin/models">模型管理</PageLink> 按「同步」拉 OpenRouter 公開模型進主檔。新模型上架後也按這顆。
            </StepCard>
            <StepCard n={3} title="設定模型分級（選用）">
              至 <PageLink href="/admin/model-tiers">模型分級</PageLink> 建 tier（例：economy / standard / premium）。
            </StepCard>
            <StepCard n={4} title="設定模型白名單">
              至 <PageLink href="/admin/allowed-models">模型白名單</PageLink> 加入允許呼叫的 <code className="font-mono">model_key</code>。不在白名單會收 <code className="font-mono">403 model_forbidden</code>。
            </StepCard>
          </div>
        </Section>

        <Section id="intake" title="向使用者收集的資訊">
          <div className="overflow-x-auto">
            <Table>
              <THead>
                <TR>
                  <TH>欄位</TH>
                  <TH>必要</TH>
                  <TH>說明</TH>
                </TR>
              </THead>
              <TBody>
                {INTAKE_FIELDS.map((r) => (
                  <TR key={r.field}>
                    <TD className="font-medium">{r.field}</TD>
                    <TD>
                      {r.required ? (
                        <Badge variant="destructive">必填</Badge>
                      ) : (
                        <Badge variant="secondary">選填</Badge>
                      )}
                    </TD>
                    <TD className="text-muted-foreground">{r.note}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          </div>
        </Section>

        <Section id="onboard" title="開通流程">
          <div className="flex flex-col gap-3">
            <StepCard n={1} title="確認部門">
              到 <PageLink href="/departments">部門管理</PageLink>。已存在直接用，沒有按「新增部門」會同步產生第 1 把 SDK Key，<strong>明文只出現一次</strong>，當場複製。
            </StepCard>
            <StepCard n={2} title="確認或建立專案">
              到 <PageLink href="/projects">專案管理</PageLink>。建好後系統產生的「代碼」就是 <code className="font-mono">X-Project-Code</code> 的值。
            </StepCard>
            <StepCard n={3} title="確認模型白名單">
              到 <PageLink href="/admin/allowed-models">模型白名單</PageLink> 確認對方要的 <code className="font-mono">model_key</code> 已在清單，沒有的話加入後到模型管理按一次「同步」。
            </StepCard>
            <StepCard n={4} title="建立使用者">
              到 <PageLink href="/users">使用者管理</PageLink> 新增，角色一律選 <code className="font-mono">user</code>，填姓名 / Email / 部門 / 員工編號。
            </StepCard>
            <StepCard n={5} title="產生 User Token">
              在使用者列表按「產生 User Token」icon。回傳的字串就是 <code className="font-mono">X-User-Token</code>，<strong>只顯示一次</strong>，當下複製保存。
            </StepCard>
            <StepCard n={6} title="安全交付">
              透過 1Password / 加密訊息 / 當面交付（<strong>不要</strong>走公開 Email 或群組）：SDK Key、User Token、Project Code 三組值，並附上「使用者使用說明」連結。
            </StepCard>
          </div>
          <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-3 text-sm">
            <p className="font-medium text-amber-700 mb-1">三者必須同部門</p>
            <p className="text-muted-foreground">
              SDK Key、User Token、Project 任一不同部門，代理端會回 <code className="font-mono">401 unauthorized</code> 或 <code className="font-mono">400 project_invalid</code>。
            </p>
          </div>
        </Section>

        <Section id="pages" title="管理頁速查">
          <div className="overflow-x-auto">
            <Table>
              <THead>
                <TR>
                  <TH>頁面</TH>
                  <TH>做什麼</TH>
                </TR>
              </THead>
              <TBody>
                <TR>
                  <TD><PageLink href="/departments">部門管理</PageLink></TD>
                  <TD>建立 / 編輯部門；展開 row 管理該部門所有 SDK Key</TD>
                </TR>
                <TR>
                  <TD><PageLink href="/projects">專案管理</PageLink></TD>
                  <TD>建立專案；代碼即 <code className="font-mono">X-Project-Code</code></TD>
                </TR>
                <TR>
                  <TD><PageLink href="/users">使用者管理</PageLink></TD>
                  <TD>建立 / 編輯使用者；產生與撤銷 User Token</TD>
                </TR>
                <TR>
                  <TD><PageLink href="/admin/models">模型管理</PageLink></TD>
                  <TD>主檔、分級、同步 OpenRouter；可依模態 tag 篩選；可一鍵「啟用全部模型」或「僅保留預設模型」(依白名單)</TD>
                </TR>
                <TR>
                  <TD><PageLink href="/admin/allowed-models">模型白名單</PageLink></TD>
                  <TD>允許呼叫的 <code className="font-mono">model_key</code>；不在清單回 403</TD>
                </TR>
                <TR>
                  <TD><PageLink href="/admin/model-tiers">模型分級</PageLink></TD>
                  <TD>tier 標示（目前僅儲存與顯示）</TD>
                </TR>
                <TR>
                  <TD><PageLink href="/openrouter-keys">OpenRouter Keys</PageLink></TD>
                  <TD>平台對外呼叫 OpenRouter 用，綁部門；明文僅見一次</TD>
                </TR>
                <TR>
                  <TD><PageLink href="/usage-logs">用量紀錄</PageLink></TD>
                  <TD>每一筆呼叫的稽核明細；可依「是否使用工具」篩選，點任一筆進詳情頁看完整 Input（含圖片）/ Output</TD>
                </TR>
                <TR>
                  <TD><PageLink href="/dashboard">儀錶板</PageLink></TD>
                  <TD>時序圖 + 部門 / 模型 / 專案 / 使用者多維度排名</TD>
                </TR>
              </TBody>
            </Table>
          </div>
        </Section>

        <Section id="ops" title="例行運維">
          <ul className="list-disc pl-5 space-y-2">
            <li>
              <strong>離職 / 轉部門：</strong>到 <PageLink href="/users">使用者管理</PageLink> 改 Email / 部門，舊 User Token 自動失效，需要時重發。SDK Key 不動（綁部門不綁人）。
            </li>
            <li>
              <strong>SDK Key 外洩：</strong>到 <PageLink href="/departments">部門管理</PageLink> 展開該部門 → 停用或刪除舊 Key → 建新的 → 通知更新。
            </li>
            <li>
              <strong>新增模型：</strong>到 <PageLink href="/admin/allowed-models">模型白名單</PageLink> 加入後，到 <PageLink href="/admin/models">模型管理</PageLink> 按一次「同步」。
            </li>
            <li>
              <strong>查單一使用者用量：</strong>到 <PageLink href="/dashboard">儀錶板</PageLink> 或 <PageLink href="/usage-logs">用量紀錄</PageLink> 依部門 / 使用者篩選。
            </li>
            <li>
              <strong>OpenRouter Key 額度滿：</strong>OpenRouter 後台確認餘額；同步動作會把餘額拉回儀錶板。
            </li>
          </ul>
        </Section>

        <Section id="security" title="安全與責任">
          <ul className="list-disc pl-5 space-y-2">
            <li>
              SDK Key、User Token、OpenRouter Key 明文都<strong>只在建立時顯示一次</strong>，沒存到就只能撤銷重發，新值立即取代舊值。
            </li>
            <li>不要用 Slack 公開頻道 / 公司群組 Email 貼明文；走 1Password 或加密訊息。</li>
            <li>
              呼叫會記錄到 <code className="font-mono">usage_logs</code>（含請求內容），提醒使用者<strong>不要在 prompt 帶個資</strong>。
            </li>
            <li>admin 帳號只給平台維運 IT；一般同事即使是主管也維持 user 角色。</li>
            <li>所有 admin 動作會寫 audit log。</li>
          </ul>
        </Section>
      </div>
    </>
  );
}
