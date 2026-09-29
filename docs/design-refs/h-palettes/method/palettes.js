// Palette definitions. Hues chosen to clash on purpose, each with a named job.
module.exports = {
  championship: {
    name: 'Championship',
    mood: 'A pro-play victory screen: molten gold trim and arcane teal magic cut across void-purple armor plating.',
    bg: '#0a0714',
    surface: '#150f24',
    surface2: '#08050f',
    surface3: '#20172f',
    ink: '#f7f1ff',
    ink2: '#d3c4ee',
    ink3: '#a794ce',
    ink4: '#8877ab',
    line: 'rgba(230, 210, 255, 0.10)',
    lineStrong: 'rgba(230, 210, 255, 0.20)',
    accent: '#ffb02e', accentHover: '#ffc65c', accentPress: '#e69518', onAccent: '#1a0f00',
    live: '#ff3b57', // capture / live indicator — blood crimson
    ok: '#1be8b5', // success / ready — arcane teal
    warn: '#ffd83f', // caution — trophy gold-yellow
    danger: '#ff5c8a', // destructive — rose
    money: '#ffd166', // dollar figures — coin gold
    stageAccent: '#4fd6ff', // camera stage gets its own arcane blue, apart from UI gold
    stageOk: '#3ddc84', stageWarn: '#f5a524', stageDanger: '#ff5c5c', stageLive: '#ff6a58',
    navWorkflow: '#1be8b5', navSell: '#ff3b57', navLibrary: '#c084ff',
  },
  driftKing: {
    name: 'Drift King',
    mood: 'A midnight touge run through the wet neon grid: tuner blue against tail-light red, acid-green smoke in a violet haze.',
    bg: '#060a16',
    surface: '#0d1424',
    surface2: '#04070f',
    surface3: '#141d33',
    ink: '#eef3ff',
    ink2: '#c1cdea',
    ink3: '#8f9cc4',
    ink4: '#727fa8',
    line: 'rgba(180, 200, 255, 0.10)',
    lineStrong: 'rgba(180, 200, 255, 0.20)',
    accent: '#33d1ff', accentHover: '#5fdcff', accentPress: '#1fb3e0', onAccent: '#03131c',
    live: '#ff3355', // tail lights
    ok: '#b6ff3c', // acid drift-smoke green
    warn: '#ffb703', // sodium amber
    danger: '#ff1f6b', // crash magenta
    money: '#d9ff5c', // yen-sign yellow-green, tuner decal color
    stageAccent: '#b26bff', stageOk: '#3ddc84', stageWarn: '#f5a524', stageDanger: '#ff5c5c', stageLive: '#ff6a58',
    navWorkflow: '#b26bff', navSell: '#ff3355', navLibrary: '#26e5c8',
  },
  overclock: {
    name: 'Overclock',
    mood: 'An arcade cabinet marquee blasting broadcast-HUD colors: red team versus blue team, green go-signal, gold on the scoreboard.',
    bg: '#0d0714',
    surface: '#180f24',
    surface2: '#0a0510',
    surface3: '#231633',
    ink: '#f6f0ff',
    ink2: '#d0bfe9',
    ink3: '#a292c6',
    ink4: '#8574a8',
    line: 'rgba(220, 190, 255, 0.10)',
    lineStrong: 'rgba(220, 190, 255, 0.20)',
    accent: '#b158ff', accentHover: '#c274ff', accentPress: '#9a3aec', onAccent: '#0d0714',
    live: '#ff3b3b', // red team
    ok: '#39ff88', // go-signal green
    warn: '#ffcb3d', // scoreboard gold
    danger: '#ff1053', // foul crimson
    money: '#ffd23d', // trophy gold
    stageAccent: '#2bd9ff', stageOk: '#3ddc84', stageWarn: '#f5a524', stageDanger: '#ff5c5c', stageLive: '#ff6a58',
    navWorkflow: '#2bd9ff', navSell: '#ff3b3b', navLibrary: '#39ff88',
  },
  lanternDistrict: {
    name: 'Lantern District',
    mood: 'A back-alley night market in the rain: red paper lanterns, matcha-neon signage, cobalt puddle reflections, ramen-stall gold.',
    bg: '#0a090f',
    surface: '#131019',
    surface2: '#07060b',
    surface3: '#1c1826',
    ink: '#f4f1fb',
    ink2: '#c9c4dc',
    ink3: '#9a94b8',
    ink4: '#7d7799',
    line: 'rgba(210, 200, 240, 0.10)',
    lineStrong: 'rgba(210, 200, 240, 0.20)',
    accent: '#4d7bff', accentHover: '#6d92ff', accentPress: '#3a63e0', onAccent: '#050710',
    live: '#ff4438', // lantern red
    ok: '#7dfb6b', // matcha neon
    warn: '#ffb238', // ramen-stall gold
    danger: '#ff2f7e', // deep red-violet
    money: '#ffd23f', // gold
    stageAccent: '#7f90ff', stageOk: '#3ddc84', stageWarn: '#f5a524', stageDanger: '#ff5c5c', stageLive: '#ff6a58',
    navWorkflow: '#4d7bff', navSell: '#ff4438', navLibrary: '#7dfb6b',
  },
};
