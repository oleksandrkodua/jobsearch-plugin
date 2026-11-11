/* Flowchart: the path of one vacancy through the jobsearch plugin, drawn as a mail-room belt.
   All counts are synthetic (made up for the drawing). The list of stations is mirrored in
   vacancy-path.json; tests/test_vacancy_path.py fails when the two, or the plugin's commands, drift apart.
   Rebuild the picture with tools/build_vacancy_path.py after any edit. */
const jsfI = '#5e5f6b';
const jsfElbow = (pts,R = 12) => { const o = [pts[0]]; for (let i = 1; i < pts.length-1; i++) o.push(...round(pts[i-1],pts[i],pts[i+1],R)); o.push(pts.at(-1)); return o; };
/* a conveyor belt with light slats */
const jsfBelt = pts => { r0.ln(pts,jsfI,13); r0.ln(pts,'#8f949b',11); r0.ln(pts,'#bcc1c6',7.5);
  out.push(`<path d="${pathOf(pts)}" fill="none" stroke="#eef0f1" stroke-width="5" stroke-dasharray="1.2 8" opacity=".8"/>`); };
/* small envelopes riding a belt */
const jsfMail = (pts,n,dur) => { const d = 'M'+pts.map(q => n1(q[0])+' '+n1(q[1])).join('L');
  for (let i = 0; i < n; i++) out.push(`<g><rect x="-5.5" y="-4" width="11" height="8" rx="1" fill="#f8f3ea" stroke="${jsfI}" stroke-width=".7"/><path d="M-5.5 -4L0 .8L5.5 -4" fill="none" stroke="${jsfI}" stroke-width=".6"/><animateMotion dur="${dur}s" begin="-${(i*dur/n).toFixed(2)}s" repeatCount="indefinite" path="${d}" calcMode="paced"/></g>`); };
/* a sheet of paper with a few written lines */
const jsfSheet = (x,y,w,h,n = 3,col = '#fbf8f1') => { const p = rrect(x,y,w,h,2); r0.part(p,col,.9,jsfI);
  rule(Array.from({length:n},(_,k) => [[x+5,y+9+k*8],[x+w-(k === n-1 ? 12 : 5),y+9+k*8]]),'#b9b3a6',.6,.8); };
const jsfCap = (x,y,name,sub) => { TX(x,y,name,{cap:true,size:15.5,anchor:'middle'}); TX(x,y+17,sub,{size:14,col:LN,anchor:'middle'}); };

card({id:'jsflow',name:'Flowchart',of:'one vacancy through the jobsearch plugin',
  note:'Follow a vacancy along the belt. The plugin prepares everything; the red postbox is the one step done by hand. Touch a station.',
  draw(){
  const I = jsfI;
  /* synthetic counts */
  const N = {found:12, apply:5, skip:7, drafts:5, sent:5, replies:2, silent:3, nudges:3};
  r0.defs(r0.lg('jsflowR',[[0,'#b8503f'],[.4,'#d06a55'],[1,'#a8463a']]),r0.lg('jsflowF',[[0,'#ecd29a'],[1,'#d3b271']],{x2:0,y2:1}));

  /* belts first, so each station sits over its belt ends */
  const R1 = [[96,120],[174,120]], R2 = [[226,120],[302,120]], R3 = [[358,120],[430,120]], R4 = [[450,150],[450,272]],
    R5 = [[422,310],[346,310]], R6 = [[294,310],[224,310]], Rs = jsfElbow([[200,148],[200,226],[70,226],[70,280]]);
  for (const r of [R1,R2,R3,R4,R5,R6,Rs]) jsfBelt(r);
  jsfMail(R1,3,3); jsfMail(R2,2,3.4); jsfMail(R3,2,3.4); jsfMail(R4,3,4.6); jsfMail(R5,2,3.6); jsfMail(R6,2,3.6); jsfMail(Rs,3,6.5);
  TX(264,108,'yes',{size:15.5,anchor:'middle'}); TX(212,196,'no',{size:15.5}); TX(384,297,'no reply',{size:13.5,anchor:'middle'});

  /* 1 scan: a pile of job postings under a magnifying glass */
  PT('scan: looks through the job boards you chose and brings back '+N.found+' new vacancies',() => {
    r0.shadow(70,150,40,4,.13);
    jsfSheet(38,96,46,52,4); jsfSheet(44,90,46,52,4,'#f6f1e6'); jsfSheet(50,84,46,52,4);
    const g = r0.el(92,132,13,13,28); r0.ln([[101,142],[113,154]],I,6.5); r0.ln([[101,142],[113,154]],'#b08a63',4.5);
    r0.sol(g,'#dfeaf0',.88); rim(g,1.5,I); r0.ln(r0.arc(92,132,8.5,8.5,200,255,8),'#f8fbfc',1.4,.9);
    jsfCap(70,36,'scan','search boards');
  },{lift:[0,-5]});

  /* 2 rank: a clipboard checklist */
  PT('rank: checks duplicates, blockers and match. '+N.apply+' of '+N.found+' go on to apply, '+N.skip+' are skipped',() => {
    r0.shadow(200,152,36,4,.13);
    r0.part(rrect(171,80,58,72,5),'#c9a877',1.1,I); r0.part(rrect(177,90,46,56,2),'#fbf8f1',.9,I);
    r0.part(rrect(188,74,24,12,3),'#a3a9af',.9,I); r0.dot(200,80,2,'#6c7178');
    for (const [y,ok] of [[104,1],[118,1],[132,0]]) {
      if (ok) r0.ln([[182,y],[185.5,y+3.5],[191,y-4]],'#6f9a6a',1.7); else { r0.ln([[183,y-3.5],[190,y+3.5]],'#a8776a',1.6); r0.ln([[190,y-3.5],[183,y+3.5]],'#a8776a',1.6); }
      rule([[[196,y],[217,y]]],'#b9b3a6',.7,.9); }
    jsfCap(200,36,'rank','triage');
  },{lift:[0,-5]});

  /* 3 apply: a folder with the CV and the letter drafts */
  PT('apply: prepares '+N.drafts+' tailored CV and cover letter drafts, each checked against your facts. Nothing is sent',() => {
    r0.shadow(330,152,38,4,.13);
    r0.part([[300,150],[300,86],[305,78],[328,78],[333,86],[360,86],[360,150]],'#cfae6c',1,I);
    jsfSheet(307,70,30,44,3); jsfSheet(325,74,30,44,3,'#f6f1e6');
    const fr = [[297,108],[363,108],[359,152],[301,152]]; r0.part(fr,'url(#jsflowF)',1.1,I);
    TX(330,137,'drafts',{size:14,anchor:'middle',col:'#7d6535'});
    jsfCap(330,36,'apply','CV and letter');
  },{lift:[0,-5]});

  /* 4 the manual step: a red postbox */
  PT('send by hand: you read the drafts and send the '+N.sent+' applications yourself. The plugin never sends or clicks Apply',() => {
    r0.shadow(450,156,34,4,.14);
    r0.part(rrect(424,146,52,9,2),'#6c7178',1,I);
    const body = [[429,148],[429,92],...r0.arc(450,92,21,14,180,360,14),[471,148]]; r0.sol(body,'url(#jsflowR)'); rim(body,1.15,I);
    r0.ln(r0.arc(450,92,21,5,10,170,12),'#93392f',.9,.8);
    r0.sol(rrect(436,102,28,6,2),'#4b3b3a'); r0.part(rrect(440,116,20,15,1.5),'#f8f3ea',.7,I);
    rule([[[443,121],[457,121]],[[443,125],[454,125]]],'#b9b3a6',.6,.9);
    r0.ln([[433,96],[433,142]],'#e9a392',1.2,.55);
    TX(450,36,'you send',{cap:true,size:15.5,anchor:'middle',col:RED}); TX(450,53,'by hand',{size:14,col:LN,anchor:'middle'});
  },{lift:[0,-5]});

  /* 5 outcome: an opened envelope with the reply */
  PT('outcome: records what came back in the tracker. Here '+N.replies+' replies and '+N.silent+' with no reply yet',() => {
    r0.shadow(450,334,38,4,.13);
    r0.part([[420,294],[450,272],[480,294]],'#e3d6bd',1,I);
    jsfSheet(431,270,38,40,3);
    const env = rrect(420,294,60,38,2); r0.part(env,'#f3ead8',1.1,I); r0.ln([[420,295],[450,316],[480,295]],I,.9);
    rule([[[420,331],[440,312]],[[480,331],[460,312]]],'#cbbfa6',.6,.9);
    jsfCap(450,358,'outcome','log the reply');
  },{lift:[0,-5]});

  /* 6 followup: a desk calendar with one day ringed */
  PT('followup: lists applications waiting too long and drafts '+N.nudges+' polite follow-ups. Drafts only',() => {
    r0.shadow(320,336,34,4,.13);
    r0.part(rrect(292,282,56,52,4),'#fbf8f1',1.1,I); r0.sol([[293,283],[347,283],[347,296],[293,296]],'#8fa9c2'); rule([[[292,296],[348,296]]],I,.8);
    for (const x of [306,334]) { r0.ln([[x,277],[x,287]],I,2.6); r0.ln([[x,277],[x,287]],'#d7dadd',1.2); }
    for (let r = 0; r < 3; r++) for (let k = 0; k < 4; k++) r0.dot(302+k*12,305+r*10,1.5,'#a9a294');
    rim(r0.el(326,315,6.2,6.2,20),1.5,RED);
    jsfCap(320,358,'followup','nudge drafts');
  },{lift:[0,-5]});

  /* 7 funnel: the report, bars to scale (4 px a vacancy) */
  PT('funnel: the report, bars to scale. '+N.found+' found, '+N.apply+' worth applying, '+N.sent+' sent, '+N.replies+' replies',() => {
    r0.shadow(195,338,36,4,.13);
    r0.part(rrect(164,270,62,66,3),'#fbf8f1',1.1,I);
    [[N.found,'#9fb8cc'],[N.apply,'#a9c0a2'],[N.sent,'#dcc184'],[N.replies,'#d9a59a']].forEach(([v,c],k) => {
      const w = v*4, y = 278+k*14; r0.part(rrect(195-w/2,y,w,10,1.5),c,.7,I); });
    jsfCap(195,358,'funnel','the report');
  },{lift:[0,-5]});

  /* the skip tray: an archive box */
  PT('skipped: '+N.skip+' vacancies with a blocker or a low match stay in the tracker and are never hidden',() => {
    r0.shadow(70,338,36,4,.13);
    jsfSheet(48,276,26,24,2); jsfSheet(58,272,26,26,2,'#f6f1e6'); jsfSheet(68,278,24,22,2);
    r0.part(rrect(40,294,60,42,3),'#b9a98a',1.1,I); r0.part(rrect(37,290,66,10,2),'#a8977a',1,I);
    r0.sol(rrect(60,312,20,7,3.5),'#6f6657'); r0.part(rrect(55,322,30,9,1.5),'#f8f3ea',.6,I);
    jsfCap(70,358,'skipped','kept on file');
  },{lift:[0,-5]});
}});
