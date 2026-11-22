"""`py-alpha-lib` 官方示例因子（**原样 vendor，别手改**）

来源：https://github.com/msd-rs/py-alpha-lib
        `examples/examples/gtja191/al/alpha191.py`
许可：BSD-2-Clause（见 `py-alpha-lib` 仓库 LICENSE）

* 每个 `alpha_NNN(ctx)` 是纯函数：输入 `alpha.context.ExecContext`，
  返回**展平面板数组**（`securityid × tradetime`，长度 = 标的数 × 根数）；
* 单标的场景由 `minibt/indicators/_alpha_factors/context.py` 按 **IndFrame 自己**
  的列构造面板（有 `securityid` / `tradetime` 就用，没有就当单标的 ✓）；
* 想把它们变成 minibt 指标请看 `scripts/gen_alpha_factors.py`。
"""


import numpy as np
# (-1 * CORR(RANK(DELTA(LOG(VOLUME), 1)), RANK(((CLOSE - OPEN) / OPEN)), 6))
def alpha_001(ctx):
  _OPEN = ctx('OPEN')
  return (-1 * ctx.CORR(ctx.RANK(ctx.DELTA(ctx.LOG(ctx('VOLUME')), 1)), ctx.RANK(((ctx('CLOSE') - _OPEN) / _OPEN)), 6))



# (-1 * DELTA((((CLOSE - LOW) - (HIGH - CLOSE)) / (HIGH - LOW)), 1))
def alpha_002(ctx):
  _CLOSE = ctx('CLOSE')
  _HIGH = ctx('HIGH')
  _LOW = ctx('LOW')
  return (-1 * ctx.DELTA((((_CLOSE - _LOW) - (_HIGH - _CLOSE)) / (_HIGH - _LOW)), 1))



# SUM((CLOSE==DELAY(CLOSE,1)?0:CLOSE-(CLOSE>DELAY(CLOSE,1)?MIN(LOW,DELAY(CLOSE,1)):MAX(HIGH,DELAY(CLOSE,1)))),6)
def alpha_003(ctx):
  _CLOSE = ctx('CLOSE')
  return ctx.SUM(np.where((_CLOSE == ctx.DELAY(_CLOSE, 1)), 0, (_CLOSE - np.where((_CLOSE > ctx.DELAY(_CLOSE, 1)), ctx.MIN(ctx('LOW'), ctx.DELAY(_CLOSE, 1)), ctx.MAX(ctx('HIGH'), ctx.DELAY(_CLOSE, 1))))), 6)



# ((((SUM(CLOSE, 8) / 8) + STD(CLOSE, 8)) < (SUM(CLOSE, 2) / 2)) ? (-1 * 1) : (((SUM(CLOSE, 2) / 2) < ((SUM(CLOSE, 8) / 8) - STD(CLOSE, 8))) ? 1 : (((1 < (VOLUME / MEAN(VOLUME,20))) || ((VOLUME / MEAN(VOLUME,20)) == 1)) ? 1 : (-1 * 1))))
def alpha_004(ctx):
  _CLOSE = ctx('CLOSE')
  _VOLUME = ctx('VOLUME')
  return np.where((((ctx.SUM(_CLOSE, 8) / 8) + ctx.STD(_CLOSE, 8)) < (ctx.SUM(_CLOSE, 2) / 2)), (-1 * 1), np.where(((ctx.SUM(_CLOSE, 2) / 2) < ((ctx.SUM(_CLOSE, 8) / 8) - ctx.STD(_CLOSE, 8))), 1, np.where(np.bitwise_or((1 < (_VOLUME / ctx.MEAN(_VOLUME, 20))), ((_VOLUME / ctx.MEAN(_VOLUME, 20)) == 1)), 1, (-1 * 1))))



# (-1 * TSMAX(CORR(TSRANK(VOLUME, 5), TSRANK(HIGH, 5), 5), 3))
def alpha_005(ctx):
  return (-1 * ctx.TSMAX(ctx.CORR(ctx.TSRANK(ctx('VOLUME'), 5), ctx.TSRANK(ctx('HIGH'), 5), 5), 3))



# (RANK(SIGN(DELTA((((OPEN * 0.85) + (HIGH * 0.15))), 4)))* -1)
def alpha_006(ctx):
  return (ctx.RANK(ctx.SIGN(ctx.DELTA(((ctx('OPEN') * 0.85) + (ctx('HIGH') * 0.15)), 4))) * -1)



# ((RANK(MAX((VWAP - CLOSE), 3)) + RANK(MIN((VWAP - CLOSE), 3))) * RANK(DELTA(VOLUME, 3)))
def alpha_007(ctx):
  _CLOSE = ctx('CLOSE')
  _VWAP = ctx('VWAP')
  return ((ctx.RANK(ctx.MAX((_VWAP - _CLOSE), 3)) + ctx.RANK(ctx.MIN((_VWAP - _CLOSE), 3))) * ctx.RANK(ctx.DELTA(ctx('VOLUME'), 3)))



# RANK(DELTA(((((HIGH + LOW) / 2) * 0.2) + (VWAP * 0.8)), 4) * -1)
def alpha_008(ctx):
  return ctx.RANK((ctx.DELTA(((((ctx('HIGH') + ctx('LOW')) / 2) * 0.2) + (ctx('VWAP') * 0.8)), 4) * -1))



# SMA(((HIGH+LOW)/2-(DELAY(HIGH,1)+DELAY(LOW,1))/2)*(HIGH-LOW)/VOLUME,7,2)
def alpha_009(ctx):
  _HIGH = ctx('HIGH')
  _LOW = ctx('LOW')
  return ctx.SMA(((((_HIGH + _LOW) / 2) - ((ctx.DELAY(_HIGH, 1) + ctx.DELAY(_LOW, 1)) / 2)) * (_HIGH - _LOW) / ctx('VOLUME')), 7, 2)



# RANK(TSMAX(((RET < 0) ? STD(RET, 20) : CLOSE)^2, 5))
def alpha_010(ctx):
  _RET = ctx('RET')
  return ctx.RANK(ctx.TSMAX(np.power(np.where((_RET < 0), ctx.STD(_RET, 20), ctx('CLOSE')), 2), 5))



# SUM(((CLOSE-LOW)-(HIGH-CLOSE))/(HIGH-LOW)*VOLUME,6)
def alpha_011(ctx):
  _CLOSE = ctx('CLOSE')
  _HIGH = ctx('HIGH')
  _LOW = ctx('LOW')
  return ctx.SUM((((_CLOSE - _LOW) - (_HIGH - _CLOSE)) / (_HIGH - _LOW) * ctx('VOLUME')), 6)



# (RANK((OPEN - (SUM(VWAP, 10) / 10)))) * (-1 * (RANK(ABS((CLOSE - VWAP)))))
def alpha_012(ctx):
  _VWAP = ctx('VWAP')
  return (ctx.RANK((ctx('OPEN') - (ctx.SUM(_VWAP, 10) / 10))) * (-1 * ctx.RANK(ctx.ABS((ctx('CLOSE') - _VWAP)))))



# (((HIGH * LOW)^0.5) - VWAP)
def alpha_013(ctx):
  return (np.power((ctx('HIGH') * ctx('LOW')), 0.5) - ctx('VWAP'))



# CLOSE-DELAY(CLOSE,5)
def alpha_014(ctx):
  _CLOSE = ctx('CLOSE')
  return (_CLOSE - ctx.DELAY(_CLOSE, 5))



# OPEN/DELAY(CLOSE,1)-1
def alpha_015(ctx):
  return ((ctx('OPEN') / ctx.DELAY(ctx('CLOSE'), 1)) - 1)



# (-1 * TSMAX(RANK(CORR(RANK(VOLUME), RANK(VWAP), 5)), 5))
def alpha_016(ctx):
  return (-1 * ctx.TSMAX(ctx.RANK(ctx.CORR(ctx.RANK(ctx('VOLUME')), ctx.RANK(ctx('VWAP')), 5)), 5))



# RANK((VWAP - MAX(VWAP, 15)))^DELTA(CLOSE, 5)
def alpha_017(ctx):
  _VWAP = ctx('VWAP')
  return np.power(ctx.RANK((_VWAP - ctx.MAX(_VWAP, 15))), ctx.DELTA(ctx('CLOSE'), 5))



# CLOSE/DELAY(CLOSE,5)
def alpha_018(ctx):
  _CLOSE = ctx('CLOSE')
  return (_CLOSE / ctx.DELAY(_CLOSE, 5))



# (CLOSE<DELAY(CLOSE,5)?(CLOSE-DELAY(CLOSE,5))/DELAY(CLOSE,5):(CLOSE==DELAY(CLOSE,5)?0:(CLOSE-DELAY(CLOSE,5))/CLOSE))
def alpha_019(ctx):
  _CLOSE = ctx('CLOSE')
  return np.where((_CLOSE < ctx.DELAY(_CLOSE, 5)), ((_CLOSE - ctx.DELAY(_CLOSE, 5)) / ctx.DELAY(_CLOSE, 5)), np.where((_CLOSE == ctx.DELAY(_CLOSE, 5)), 0, ((_CLOSE - ctx.DELAY(_CLOSE, 5)) / _CLOSE)))



# (CLOSE-DELAY(CLOSE,6))/DELAY(CLOSE,6)*100
def alpha_020(ctx):
  _CLOSE = ctx('CLOSE')
  return ((_CLOSE - ctx.DELAY(_CLOSE, 6)) / ctx.DELAY(_CLOSE, 6) * 100)



# REGBETA(MEAN(CLOSE,6),SEQUENCE,6)
def alpha_021(ctx):
  return ctx.REGBETA(ctx.MEAN(ctx('CLOSE'), 6), ctx('SEQUENCE'), 6)



# SMA(((CLOSE-MEAN(CLOSE,6))/MEAN(CLOSE,6)-DELAY((CLOSE-MEAN(CLOSE,6))/MEAN(CLOSE,6),3)),12,1)
def alpha_022(ctx):
  _CLOSE = ctx('CLOSE')
  return ctx.SMA((((_CLOSE - ctx.MEAN(_CLOSE, 6)) / ctx.MEAN(_CLOSE, 6)) - ctx.DELAY(((_CLOSE - ctx.MEAN(_CLOSE, 6)) / ctx.MEAN(_CLOSE, 6)), 3)), 12, 1)



# SMA((CLOSE>DELAY(CLOSE,1)?STD(CLOSE,20):0),20,1)/(SMA((CLOSE>DELAY(CLOSE,1)?STD(CLOSE,20):0),20,1 )+SMA((CLOSE<=DELAY(CLOSE,1)?STD(CLOSE,20):0),20,1))*100
def alpha_023(ctx):
  _CLOSE = ctx('CLOSE')
  return (ctx.SMA(np.where((_CLOSE > ctx.DELAY(_CLOSE, 1)), ctx.STD(_CLOSE, 20), 0), 20, 1) / (ctx.SMA(np.where((_CLOSE > ctx.DELAY(_CLOSE, 1)), ctx.STD(_CLOSE, 20), 0), 20, 1) + ctx.SMA(np.where((_CLOSE <= ctx.DELAY(_CLOSE, 1)), ctx.STD(_CLOSE, 20), 0), 20, 1)) * 100)



# SMA(CLOSE-DELAY(CLOSE,5),5,1)
def alpha_024(ctx):
  _CLOSE = ctx('CLOSE')
  return ctx.SMA((_CLOSE - ctx.DELAY(_CLOSE, 5)), 5, 1)



# ((-1 * RANK((DELTA(CLOSE, 7) * (1 - RANK(DECAYLINEAR((VOLUME / MEAN(VOLUME,20)), 9)))))) * (1 + RANK(SUM(RET, 250))))
def alpha_025(ctx):
  _VOLUME = ctx('VOLUME')
  return ((-1 * ctx.RANK((ctx.DELTA(ctx('CLOSE'), 7) * (1 - ctx.RANK(ctx.DECAYLINEAR((_VOLUME / ctx.MEAN(_VOLUME, 20)), 9)))))) * (1 + ctx.RANK(ctx.SUM(ctx('RET'), 250))))



# ((((SUM(CLOSE, 7) / 7) - CLOSE)) + ((CORR(VWAP, DELAY(CLOSE, 5), 230))))
def alpha_026(ctx):
  _CLOSE = ctx('CLOSE')
  return (((ctx.SUM(_CLOSE, 7) / 7) - _CLOSE) + ctx.CORR(ctx('VWAP'), ctx.DELAY(_CLOSE, 5), 230))



# WMA((CLOSE-DELAY(CLOSE,3))/DELAY(CLOSE,3)*100+(CLOSE-DELAY(CLOSE,6))/DELAY(CLOSE,6)*100,12)
def alpha_027(ctx):
  _CLOSE = ctx('CLOSE')
  return ctx.WMA((((_CLOSE - ctx.DELAY(_CLOSE, 3)) / ctx.DELAY(_CLOSE, 3) * 100) + ((_CLOSE - ctx.DELAY(_CLOSE, 6)) / ctx.DELAY(_CLOSE, 6) * 100)), 12)



# 3*SMA((CLOSE-TSMIN(LOW,9))/(TSMAX(HIGH,9)-TSMIN(LOW,9))*100,3,1)-2*SMA(SMA((CLOSE-TSMIN(LOW,9))/(MAX(HIGH,9)-TSMAX(LOW,9))*100,3,1),3,1)
def alpha_028(ctx):
  _CLOSE = ctx('CLOSE')
  _HIGH = ctx('HIGH')
  _LOW = ctx('LOW')
  return ((3 * ctx.SMA(((_CLOSE - ctx.TSMIN(_LOW, 9)) / (ctx.TSMAX(_HIGH, 9) - ctx.TSMIN(_LOW, 9)) * 100), 3, 1)) - (2 * ctx.SMA(ctx.SMA(((_CLOSE - ctx.TSMIN(_LOW, 9)) / (ctx.MAX(_HIGH, 9) - ctx.TSMAX(_LOW, 9)) * 100), 3, 1), 3, 1)))



# (CLOSE-DELAY(CLOSE,6))/DELAY(CLOSE,6)*VOLUME
def alpha_029(ctx):
  _CLOSE = ctx('CLOSE')
  return ((_CLOSE - ctx.DELAY(_CLOSE, 6)) / ctx.DELAY(_CLOSE, 6) * ctx('VOLUME'))



# WMA((REGRESI(CLOSE/DELAY(CLOSE)-1,MKT,SMB,HML,60))^2,20)
def alpha_030(ctx):
  _CLOSE = ctx('CLOSE')
  return ctx.WMA(np.power(ctx.REGRESI(((_CLOSE / ctx.DELAY(_CLOSE)) - 1), ctx('MKT'), ctx('SMB'), ctx('HML'), 60), 2), 20)



# (CLOSE-MEAN(CLOSE,12))/MEAN(CLOSE,12)*100
def alpha_031(ctx):
  _CLOSE = ctx('CLOSE')
  return ((_CLOSE - ctx.MEAN(_CLOSE, 12)) / ctx.MEAN(_CLOSE, 12) * 100)



# (-1 * SUM(RANK(CORR(RANK(HIGH), RANK(VOLUME), 3)), 3))
def alpha_032(ctx):
  return (-1 * ctx.SUM(ctx.RANK(ctx.CORR(ctx.RANK(ctx('HIGH')), ctx.RANK(ctx('VOLUME')), 3)), 3))



# ((((-1 * TSMIN(LOW, 5)) + DELAY(TSMIN(LOW, 5), 5)) * RANK(((SUM(RET, 240) - SUM(RET, 20)) / 220))) * TSRANK(VOLUME, 5))
def alpha_033(ctx):
  _LOW = ctx('LOW')
  _RET = ctx('RET')
  return ((((-1 * ctx.TSMIN(_LOW, 5)) + ctx.DELAY(ctx.TSMIN(_LOW, 5), 5)) * ctx.RANK(((ctx.SUM(_RET, 240) - ctx.SUM(_RET, 20)) / 220))) * ctx.TSRANK(ctx('VOLUME'), 5))



# MEAN(CLOSE,12)/CLOSE
def alpha_034(ctx):
  _CLOSE = ctx('CLOSE')
  return (ctx.MEAN(_CLOSE, 12) / _CLOSE)



# (MIN(RANK(DECAYLINEAR(DELTA(OPEN, 1), 15)), RANK(DECAYLINEAR(CORR((VOLUME), ((OPEN * 0.65) + (OPEN *0.35)), 17),7))) * -1)
def alpha_035(ctx):
  _OPEN = ctx('OPEN')
  return (ctx.MIN(ctx.RANK(ctx.DECAYLINEAR(ctx.DELTA(_OPEN, 1), 15)), ctx.RANK(ctx.DECAYLINEAR(ctx.CORR(ctx('VOLUME'), ((_OPEN * 0.65) + (_OPEN * 0.35)), 17), 7))) * -1)



# RANK(SUM(CORR(RANK(VOLUME), RANK(VWAP), 6), 2))
def alpha_036(ctx):
  return ctx.RANK(ctx.SUM(ctx.CORR(ctx.RANK(ctx('VOLUME')), ctx.RANK(ctx('VWAP')), 6), 2))



# (-1 * RANK(((SUM(OPEN, 5) * SUM(RET, 5)) - DELAY((SUM(OPEN, 5) * SUM(RET, 5)), 10))))
def alpha_037(ctx):
  _OPEN = ctx('OPEN')
  _RET = ctx('RET')
  return (-1 * ctx.RANK(((ctx.SUM(_OPEN, 5) * ctx.SUM(_RET, 5)) - ctx.DELAY((ctx.SUM(_OPEN, 5) * ctx.SUM(_RET, 5)), 10))))



# (((SUM(HIGH, 20) / 20) < HIGH) ? (-1 * DELTA(HIGH, 2)) : 0)
def alpha_038(ctx):
  _HIGH = ctx('HIGH')
  return np.where(((ctx.SUM(_HIGH, 20) / 20) < _HIGH), (-1 * ctx.DELTA(_HIGH, 2)), 0)



# ((RANK(DECAYLINEAR(DELTA((CLOSE), 2),8)) - RANK(DECAYLINEAR(CORR(((VWAP * 0.3) + (OPEN * 0.7)), SUM(MEAN(VOLUME,180), 37), 14), 12))) * -1)
def alpha_039(ctx):
  return ((ctx.RANK(ctx.DECAYLINEAR(ctx.DELTA(ctx('CLOSE'), 2), 8)) - ctx.RANK(ctx.DECAYLINEAR(ctx.CORR(((ctx('VWAP') * 0.3) + (ctx('OPEN') * 0.7)), ctx.SUM(ctx.MEAN(ctx('VOLUME'), 180), 37), 14), 12))) * -1)



# SUM((CLOSE>DELAY(CLOSE,1)?VOLUME:0),26)/SUM((CLOSE<=DELAY(CLOSE,1)?VOLUME:0),26)*100
def alpha_040(ctx):
  _CLOSE = ctx('CLOSE')
  _VOLUME = ctx('VOLUME')
  return (ctx.SUM(np.where((_CLOSE > ctx.DELAY(_CLOSE, 1)), _VOLUME, 0), 26) / ctx.SUM(np.where((_CLOSE <= ctx.DELAY(_CLOSE, 1)), _VOLUME, 0), 26) * 100)



# (RANK(MAX(DELTA((VWAP), 3), 5))* -1)
def alpha_041(ctx):
  return (ctx.RANK(ctx.MAX(ctx.DELTA(ctx('VWAP'), 3), 5)) * -1)



# ((-1 * RANK(STD(HIGH, 10))) * CORR(HIGH, VOLUME, 10))
def alpha_042(ctx):
  _HIGH = ctx('HIGH')
  return ((-1 * ctx.RANK(ctx.STD(_HIGH, 10))) * ctx.CORR(_HIGH, ctx('VOLUME'), 10))



# SUM((CLOSE>DELAY(CLOSE,1)?VOLUME:(CLOSE<DELAY(CLOSE,1)?-VOLUME:0)),6)
def alpha_043(ctx):
  _CLOSE = ctx('CLOSE')
  _VOLUME = ctx('VOLUME')
  return ctx.SUM(np.where((_CLOSE > ctx.DELAY(_CLOSE, 1)), _VOLUME, np.where((_CLOSE < ctx.DELAY(_CLOSE, 1)), -_VOLUME, 0)), 6)



# (TSRANK(DECAYLINEAR(CORR(((LOW )), MEAN(VOLUME,10), 7), 6),4) + TSRANK(DECAYLINEAR(DELTA((VWAP), 3), 10), 15))
def alpha_044(ctx):
  return (ctx.TSRANK(ctx.DECAYLINEAR(ctx.CORR(ctx('LOW'), ctx.MEAN(ctx('VOLUME'), 10), 7), 6), 4) + ctx.TSRANK(ctx.DECAYLINEAR(ctx.DELTA(ctx('VWAP'), 3), 10), 15))



# (RANK(DELTA((((CLOSE * 0.6) + (OPEN *0.4))), 1)) * RANK(CORR(VWAP, MEAN(VOLUME,150), 15)))
def alpha_045(ctx):
  return (ctx.RANK(ctx.DELTA(((ctx('CLOSE') * 0.6) + (ctx('OPEN') * 0.4)), 1)) * ctx.RANK(ctx.CORR(ctx('VWAP'), ctx.MEAN(ctx('VOLUME'), 150), 15)))



# (MEAN(CLOSE,3)+MEAN(CLOSE,6)+MEAN(CLOSE,12)+MEAN(CLOSE,24))/(4*CLOSE)
def alpha_046(ctx):
  _CLOSE = ctx('CLOSE')
  return ((ctx.MEAN(_CLOSE, 3) + ctx.MEAN(_CLOSE, 6) + ctx.MEAN(_CLOSE, 12) + ctx.MEAN(_CLOSE, 24)) / (4 * _CLOSE))



# SMA((TSMAX(HIGH,6)-CLOSE)/(TSMAX(HIGH,6)-TSMIN(LOW,6))*100,9,1)
def alpha_047(ctx):
  _HIGH = ctx('HIGH')
  return ctx.SMA(((ctx.TSMAX(_HIGH, 6) - ctx('CLOSE')) / (ctx.TSMAX(_HIGH, 6) - ctx.TSMIN(ctx('LOW'), 6)) * 100), 9, 1)



# (-1*((RANK(((SIGN((CLOSE - DELAY(CLOSE, 1))) + SIGN((DELAY(CLOSE, 1) - DELAY(CLOSE, 2)))) + SIGN((DELAY(CLOSE, 2) - DELAY(CLOSE, 3)))))) * SUM(VOLUME, 5)) / SUM(VOLUME, 20))
def alpha_048(ctx):
  _CLOSE = ctx('CLOSE')
  _VOLUME = ctx('VOLUME')
  return (-1 * (ctx.RANK(((ctx.SIGN((_CLOSE - ctx.DELAY(_CLOSE, 1))) + ctx.SIGN((ctx.DELAY(_CLOSE, 1) - ctx.DELAY(_CLOSE, 2)))) + ctx.SIGN((ctx.DELAY(_CLOSE, 2) - ctx.DELAY(_CLOSE, 3))))) * ctx.SUM(_VOLUME, 5)) / ctx.SUM(_VOLUME, 20))



# SUM(((HIGH+LOW)>=(DELAY(HIGH,1)+DELAY(LOW,1))?0:MAX(ABS(HIGH-DELAY(HIGH,1)),ABS(LOW-DELAY(LOW,1)))),12)/(SUM(((HIGH+LOW)>=(DELAY(HIGH,1)+DELAY(LOW,1))?0:MAX(ABS(HIGH-DELAY(HIGH,1)),ABS(LOW-DELAY(LOW,1)))),12)+SUM(((HIGH+LOW)<=(DELAY(HIGH,1)+DELAY(LOW,1))?0:MAX(ABS(HIGH-DELAY(HIGH,1)),ABS(LOW-DELAY(LOW,1)))),12))
def alpha_049(ctx):
  _HIGH = ctx('HIGH')
  _LOW = ctx('LOW')
  return (ctx.SUM(np.where(((_HIGH + _LOW) >= (ctx.DELAY(_HIGH, 1) + ctx.DELAY(_LOW, 1))), 0, ctx.MAX(ctx.ABS((_HIGH - ctx.DELAY(_HIGH, 1))), ctx.ABS((_LOW - ctx.DELAY(_LOW, 1))))), 12) / (ctx.SUM(np.where(((_HIGH + _LOW) >= (ctx.DELAY(_HIGH, 1) + ctx.DELAY(_LOW, 1))), 0, ctx.MAX(ctx.ABS((_HIGH - ctx.DELAY(_HIGH, 1))), ctx.ABS((_LOW - ctx.DELAY(_LOW, 1))))), 12) + ctx.SUM(np.where(((_HIGH + _LOW) <= (ctx.DELAY(_HIGH, 1) + ctx.DELAY(_LOW, 1))), 0, ctx.MAX(ctx.ABS((_HIGH - ctx.DELAY(_HIGH, 1))), ctx.ABS((_LOW - ctx.DELAY(_LOW, 1))))), 12)))



# SUM(((HIGH+LOW)<=(DELAY(HIGH,1)+DELAY(LOW,1))?0:MAX(ABS(HIGH-DELAY(HIGH,1)),ABS(LOW-DELAY(LOW,1)))),12)/(SUM(((HIGH+LOW)<=(DELAY(HIGH,1)+DELAY(LOW,1))?0:MAX(ABS(HIGH-DELAY(HIGH,1)),ABS(LOW-DELAY(LOW,1)))),12)+SUM(((HIGH+LOW)>=(DELAY(HIGH,1)+DELAY(LOW,1))?0:MAX(ABS(HIGH-DELAY(HIGH,1)),ABS(LOW-DELAY(LOW,1)))),12))-SUM(((HIGH+LOW)>=(DELAY(HIGH,1)+DELAY(LOW,1))?0:MAX(ABS(HIGH-DELAY(HIGH,1)),ABS(LOW-DELAY(LOW,1)))),12)/(SUM(((HIGH+LOW)>=(DELAY(HIGH,1)+DELAY(LOW,1))?0:MAX(ABS(HIGH-DELAY(HIGH,1)),ABS(LOW-DELAY(LOW,1)))),12)+SUM(((HIGH+LOW)<=(DELAY(HIGH,1)+DELAY(LOW,1))?0:MAX(ABS(HIGH-DELAY(HIGH,1)),ABS(LOW-DELAY(LOW,1)))),12))
def alpha_050(ctx):
  _HIGH = ctx('HIGH')
  _LOW = ctx('LOW')
  return ((ctx.SUM(np.where(((_HIGH + _LOW) <= (ctx.DELAY(_HIGH, 1) + ctx.DELAY(_LOW, 1))), 0, ctx.MAX(ctx.ABS((_HIGH - ctx.DELAY(_HIGH, 1))), ctx.ABS((_LOW - ctx.DELAY(_LOW, 1))))), 12) / (ctx.SUM(np.where(((_HIGH + _LOW) <= (ctx.DELAY(_HIGH, 1) + ctx.DELAY(_LOW, 1))), 0, ctx.MAX(ctx.ABS((_HIGH - ctx.DELAY(_HIGH, 1))), ctx.ABS((_LOW - ctx.DELAY(_LOW, 1))))), 12) + ctx.SUM(np.where(((_HIGH + _LOW) >= (ctx.DELAY(_HIGH, 1) + ctx.DELAY(_LOW, 1))), 0, ctx.MAX(ctx.ABS((_HIGH - ctx.DELAY(_HIGH, 1))), ctx.ABS((_LOW - ctx.DELAY(_LOW, 1))))), 12))) - (ctx.SUM(np.where(((_HIGH + _LOW) >= (ctx.DELAY(_HIGH, 1) + ctx.DELAY(_LOW, 1))), 0, ctx.MAX(ctx.ABS((_HIGH - ctx.DELAY(_HIGH, 1))), ctx.ABS((_LOW - ctx.DELAY(_LOW, 1))))), 12) / (ctx.SUM(np.where(((_HIGH + _LOW) >= (ctx.DELAY(_HIGH, 1) + ctx.DELAY(_LOW, 1))), 0, ctx.MAX(ctx.ABS((_HIGH - ctx.DELAY(_HIGH, 1))), ctx.ABS((_LOW - ctx.DELAY(_LOW, 1))))), 12) + ctx.SUM(np.where(((_HIGH + _LOW) <= (ctx.DELAY(_HIGH, 1) + ctx.DELAY(_LOW, 1))), 0, ctx.MAX(ctx.ABS((_HIGH - ctx.DELAY(_HIGH, 1))), ctx.ABS((_LOW - ctx.DELAY(_LOW, 1))))), 12))))



# SUM(((HIGH+LOW)<=(DELAY(HIGH,1)+DELAY(LOW,1))?0:MAX(ABS(HIGH-DELAY(HIGH,1)),ABS(LOW-DELAY(LOW,1)))),12)/(SUM(((HIGH+LOW)<=(DELAY(HIGH,1)+DELAY(LOW,1))?0:MAX(ABS(HIGH-DELAY(HIGH,1)),ABS(LOW-DELAY(LOW,1)))),12)+SUM(((HIGH+LOW)>=(DELAY(HIGH,1)+DELAY(LOW,1))?0:MAX(ABS(HIGH-DELAY(HIGH,1)),ABS(LOW-DELAY(LOW,1)))),12))
def alpha_051(ctx):
  _HIGH = ctx('HIGH')
  _LOW = ctx('LOW')
  return (ctx.SUM(np.where(((_HIGH + _LOW) <= (ctx.DELAY(_HIGH, 1) + ctx.DELAY(_LOW, 1))), 0, ctx.MAX(ctx.ABS((_HIGH - ctx.DELAY(_HIGH, 1))), ctx.ABS((_LOW - ctx.DELAY(_LOW, 1))))), 12) / (ctx.SUM(np.where(((_HIGH + _LOW) <= (ctx.DELAY(_HIGH, 1) + ctx.DELAY(_LOW, 1))), 0, ctx.MAX(ctx.ABS((_HIGH - ctx.DELAY(_HIGH, 1))), ctx.ABS((_LOW - ctx.DELAY(_LOW, 1))))), 12) + ctx.SUM(np.where(((_HIGH + _LOW) >= (ctx.DELAY(_HIGH, 1) + ctx.DELAY(_LOW, 1))), 0, ctx.MAX(ctx.ABS((_HIGH - ctx.DELAY(_HIGH, 1))), ctx.ABS((_LOW - ctx.DELAY(_LOW, 1))))), 12)))



# SUM(MAX(0,HIGH-DELAY((HIGH+LOW+CLOSE)/3,1)),26)/SUM(MAX(0,DELAY((HIGH+LOW+CLOSE)/3,1)-LOW),26)* 100
def alpha_052(ctx):
  _CLOSE = ctx('CLOSE')
  _HIGH = ctx('HIGH')
  _LOW = ctx('LOW')
  return (ctx.SUM(ctx.MAX(0, (_HIGH - ctx.DELAY(((_HIGH + _LOW + _CLOSE) / 3), 1))), 26) / ctx.SUM(ctx.MAX(0, (ctx.DELAY(((_HIGH + _LOW + _CLOSE) / 3), 1) - _LOW)), 26) * 100)



# COUNT(CLOSE>DELAY(CLOSE,1),12)/12*100
def alpha_053(ctx):
  _CLOSE = ctx('CLOSE')
  return (ctx.COUNT((_CLOSE > ctx.DELAY(_CLOSE, 1)), 12) / 12 * 100)



# (-1 * RANK((STD(ABS(CLOSE - OPEN), 10) + (CLOSE - OPEN)) + CORR(CLOSE, OPEN, 10)))
def alpha_054(ctx):
  _CLOSE = ctx('CLOSE')
  _OPEN = ctx('OPEN')
  return (-1 * ctx.RANK(((ctx.STD(ctx.ABS((_CLOSE - _OPEN)), 10) + (_CLOSE - _OPEN)) + ctx.CORR(_CLOSE, _OPEN, 10))))



# SUM(16*(CLOSE-DELAY(CLOSE,1)+(CLOSE-OPEN)/2+DELAY(CLOSE,1)-DELAY(OPEN,1))/((ABS(HIGH-DELAY(CLOSE,1))>ABS(LOW-DELAY(CLOSE,1)) && ABS(HIGH-DELAY(CLOSE,1))>ABS(HIGH-DELAY(LOW,1))?ABS(HIGH-DELAY(CLOSE,1))+ABS(LOW-DELAY(CLOSE,1))/2+ABS(DELAY(CLOSE,1)-DELAY(OPEN,1))/4:(ABS(LOW-DELAY(CLOSE,1))>ABS(HIGH-DELAY(LOW,1)) && ABS(LOW-DELAY(CLOSE,1))>ABS(HIGH-DELAY(CLOSE,1))?ABS(LOW-DELAY(CLOSE,1))+ABS(HIGH-DELAY(CLOSE,1))/2+ABS(DELAY(CLOSE,1)-DELAY(OPEN,1))/4:ABS(HIGH-DELAY(LOW,1))+ABS(DELAY(CLOSE,1)-DELAY(OPEN,1))/4)))*MAX(ABS(HIGH-DELAY(CLOSE,1)),ABS(LOW-DELAY(CLOSE,1))),20)
def alpha_055(ctx):
  _CLOSE = ctx('CLOSE')
  _HIGH = ctx('HIGH')
  _LOW = ctx('LOW')
  _OPEN = ctx('OPEN')
  return ctx.SUM((16 * (_CLOSE - ctx.DELAY(_CLOSE, 1) + ((_CLOSE - _OPEN) / 2) + ctx.DELAY(_CLOSE, 1) - ctx.DELAY(_OPEN, 1)) / np.where(np.bitwise_and((ctx.ABS((_HIGH - ctx.DELAY(_CLOSE, 1))) > ctx.ABS((_LOW - ctx.DELAY(_CLOSE, 1)))), (ctx.ABS((_HIGH - ctx.DELAY(_CLOSE, 1))) > ctx.ABS((_HIGH - ctx.DELAY(_LOW, 1))))), (ctx.ABS((_HIGH - ctx.DELAY(_CLOSE, 1))) + (ctx.ABS((_LOW - ctx.DELAY(_CLOSE, 1))) / 2) + (ctx.ABS((ctx.DELAY(_CLOSE, 1) - ctx.DELAY(_OPEN, 1))) / 4)), np.where(np.bitwise_and((ctx.ABS((_LOW - ctx.DELAY(_CLOSE, 1))) > ctx.ABS((_HIGH - ctx.DELAY(_LOW, 1)))), (ctx.ABS((_LOW - ctx.DELAY(_CLOSE, 1))) > ctx.ABS((_HIGH - ctx.DELAY(_CLOSE, 1))))), (ctx.ABS((_LOW - ctx.DELAY(_CLOSE, 1))) + (ctx.ABS((_HIGH - ctx.DELAY(_CLOSE, 1))) / 2) + (ctx.ABS((ctx.DELAY(_CLOSE, 1) - ctx.DELAY(_OPEN, 1))) / 4)), (ctx.ABS((_HIGH - ctx.DELAY(_LOW, 1))) + (ctx.ABS((ctx.DELAY(_CLOSE, 1) - ctx.DELAY(_OPEN, 1))) / 4)))) * ctx.MAX(ctx.ABS((_HIGH - ctx.DELAY(_CLOSE, 1))), ctx.ABS((_LOW - ctx.DELAY(_CLOSE, 1))))), 20)



# (RANK((OPEN - TSMIN(OPEN, 12))) < RANK((RANK(CORR(SUM(((HIGH + LOW) / 2), 19), SUM(MEAN(VOLUME,40), 19), 13))^5)))
def alpha_056(ctx):
  _OPEN = ctx('OPEN')
  return (ctx.RANK((_OPEN - ctx.TSMIN(_OPEN, 12))) < ctx.RANK(np.power(ctx.RANK(ctx.CORR(ctx.SUM(((ctx('HIGH') + ctx('LOW')) / 2), 19), ctx.SUM(ctx.MEAN(ctx('VOLUME'), 40), 19), 13)), 5)))



# SMA((CLOSE-TSMIN(LOW,9))/(TSMAX(HIGH,9)-TSMIN(LOW,9))*100,3,1)
def alpha_057(ctx):
  _LOW = ctx('LOW')
  return ctx.SMA(((ctx('CLOSE') - ctx.TSMIN(_LOW, 9)) / (ctx.TSMAX(ctx('HIGH'), 9) - ctx.TSMIN(_LOW, 9)) * 100), 3, 1)



# COUNT(CLOSE>DELAY(CLOSE,1),20)/20*100
def alpha_058(ctx):
  _CLOSE = ctx('CLOSE')
  return (ctx.COUNT((_CLOSE > ctx.DELAY(_CLOSE, 1)), 20) / 20 * 100)



# SUM((CLOSE==DELAY(CLOSE,1)?0:CLOSE-(CLOSE>DELAY(CLOSE,1)?MIN(LOW,DELAY(CLOSE,1)):MAX(HIGH,DELAY(CLOSE,1)))),20)
def alpha_059(ctx):
  _CLOSE = ctx('CLOSE')
  return ctx.SUM(np.where((_CLOSE == ctx.DELAY(_CLOSE, 1)), 0, (_CLOSE - np.where((_CLOSE > ctx.DELAY(_CLOSE, 1)), ctx.MIN(ctx('LOW'), ctx.DELAY(_CLOSE, 1)), ctx.MAX(ctx('HIGH'), ctx.DELAY(_CLOSE, 1))))), 20)



# SUM(((CLOSE-LOW)-(HIGH-CLOSE))/(HIGH-LOW)*VOLUME,20)
def alpha_060(ctx):
  _CLOSE = ctx('CLOSE')
  _HIGH = ctx('HIGH')
  _LOW = ctx('LOW')
  return ctx.SUM((((_CLOSE - _LOW) - (_HIGH - _CLOSE)) / (_HIGH - _LOW) * ctx('VOLUME')), 20)



# (MAX(RANK(DECAYLINEAR(DELTA(VWAP, 1), 12)), RANK(DECAYLINEAR(RANK(CORR((LOW),MEAN(VOLUME,80), 8)), 17))) * -1)
def alpha_061(ctx):
  return (ctx.MAX(ctx.RANK(ctx.DECAYLINEAR(ctx.DELTA(ctx('VWAP'), 1), 12)), ctx.RANK(ctx.DECAYLINEAR(ctx.RANK(ctx.CORR(ctx('LOW'), ctx.MEAN(ctx('VOLUME'), 80), 8)), 17))) * -1)



# (-1 * CORR(HIGH, RANK(VOLUME), 5))
def alpha_062(ctx):
  return (-1 * ctx.CORR(ctx('HIGH'), ctx.RANK(ctx('VOLUME')), 5))



# SMA(MAX(CLOSE-DELAY(CLOSE,1),0),6,1)/SMA(ABS(CLOSE-DELAY(CLOSE,1)),6,1)*100
def alpha_063(ctx):
  _CLOSE = ctx('CLOSE')
  return (ctx.SMA(ctx.MAX((_CLOSE - ctx.DELAY(_CLOSE, 1)), 0), 6, 1) / ctx.SMA(ctx.ABS((_CLOSE - ctx.DELAY(_CLOSE, 1))), 6, 1) * 100)



# (MAX(RANK(DECAYLINEAR(CORR(RANK(VWAP), RANK(VOLUME), 4), 4)), RANK(DECAYLINEAR(MAX(CORR(RANK(CLOSE), RANK(MEAN(VOLUME,60)), 4), 13), 14))) * -1)
def alpha_064(ctx):
  _VOLUME = ctx('VOLUME')
  return (ctx.MAX(ctx.RANK(ctx.DECAYLINEAR(ctx.CORR(ctx.RANK(ctx('VWAP')), ctx.RANK(_VOLUME), 4), 4)), ctx.RANK(ctx.DECAYLINEAR(ctx.MAX(ctx.CORR(ctx.RANK(ctx('CLOSE')), ctx.RANK(ctx.MEAN(_VOLUME, 60)), 4), 13), 14))) * -1)



# MEAN(CLOSE,6)/CLOSE
def alpha_065(ctx):
  _CLOSE = ctx('CLOSE')
  return (ctx.MEAN(_CLOSE, 6) / _CLOSE)



# (CLOSE-MEAN(CLOSE,6))/MEAN(CLOSE,6)*100
def alpha_066(ctx):
  _CLOSE = ctx('CLOSE')
  return ((_CLOSE - ctx.MEAN(_CLOSE, 6)) / ctx.MEAN(_CLOSE, 6) * 100)



# SMA(MAX(CLOSE-DELAY(CLOSE,1),0),24,1)/SMA(ABS(CLOSE-DELAY(CLOSE,1)),24,1)*100
def alpha_067(ctx):
  _CLOSE = ctx('CLOSE')
  return (ctx.SMA(ctx.MAX((_CLOSE - ctx.DELAY(_CLOSE, 1)), 0), 24, 1) / ctx.SMA(ctx.ABS((_CLOSE - ctx.DELAY(_CLOSE, 1))), 24, 1) * 100)



# SMA(((HIGH+LOW)/2-(DELAY(HIGH,1)+DELAY(LOW,1))/2)*(HIGH-LOW)/VOLUME,15,2)
def alpha_068(ctx):
  _HIGH = ctx('HIGH')
  _LOW = ctx('LOW')
  return ctx.SMA(((((_HIGH + _LOW) / 2) - ((ctx.DELAY(_HIGH, 1) + ctx.DELAY(_LOW, 1)) / 2)) * (_HIGH - _LOW) / ctx('VOLUME')), 15, 2)



# (SUM(DTM,20)>SUM(DBM,20) ? (SUM(DTM,20)-SUM(DBM,20))/SUM(DTM,20) : (SUM(DTM,20)==SUM(DBM,20) ? 0:(SUM(DTM,20)-SUM(DBM,20))/SUM(DBM,20)))
def alpha_069(ctx):
  _DBM = ctx('DBM')
  _DTM = ctx('DTM')
  return np.where((ctx.SUM(_DTM, 20) > ctx.SUM(_DBM, 20)), ((ctx.SUM(_DTM, 20) - ctx.SUM(_DBM, 20)) / ctx.SUM(_DTM, 20)), np.where((ctx.SUM(_DTM, 20) == ctx.SUM(_DBM, 20)), 0, ((ctx.SUM(_DTM, 20) - ctx.SUM(_DBM, 20)) / ctx.SUM(_DBM, 20))))



# STD(AMOUNT,6)
def alpha_070(ctx):
  return ctx.STD(ctx('AMOUNT'), 6)



# (CLOSE-MEAN(CLOSE,24))/MEAN(CLOSE,24)*100
def alpha_071(ctx):
  _CLOSE = ctx('CLOSE')
  return ((_CLOSE - ctx.MEAN(_CLOSE, 24)) / ctx.MEAN(_CLOSE, 24) * 100)



# SMA((TSMAX(HIGH,6)-CLOSE)/(TSMAX(HIGH,6)-TSMIN(LOW,6))*100,15,1)
def alpha_072(ctx):
  _HIGH = ctx('HIGH')
  return ctx.SMA(((ctx.TSMAX(_HIGH, 6) - ctx('CLOSE')) / (ctx.TSMAX(_HIGH, 6) - ctx.TSMIN(ctx('LOW'), 6)) * 100), 15, 1)



# ((TSRANK(DECAYLINEAR(DECAYLINEAR(CORR((CLOSE), VOLUME, 10), 16), 4), 5) - RANK(DECAYLINEAR(CORR(VWAP, MEAN(VOLUME,30), 4),3))) * -1)
def alpha_073(ctx):
  _VOLUME = ctx('VOLUME')
  return ((ctx.TSRANK(ctx.DECAYLINEAR(ctx.DECAYLINEAR(ctx.CORR(ctx('CLOSE'), _VOLUME, 10), 16), 4), 5) - ctx.RANK(ctx.DECAYLINEAR(ctx.CORR(ctx('VWAP'), ctx.MEAN(_VOLUME, 30), 4), 3))) * -1)



# (RANK(CORR(SUM(((LOW * 0.35) + (VWAP * 0.65)), 20), SUM(MEAN(VOLUME,40), 20), 7)) + RANK(CORR(RANK(VWAP), RANK(VOLUME), 6)))
def alpha_074(ctx):
  _VOLUME = ctx('VOLUME')
  _VWAP = ctx('VWAP')
  return (ctx.RANK(ctx.CORR(ctx.SUM(((ctx('LOW') * 0.35) + (_VWAP * 0.65)), 20), ctx.SUM(ctx.MEAN(_VOLUME, 40), 20), 7)) + ctx.RANK(ctx.CORR(ctx.RANK(_VWAP), ctx.RANK(_VOLUME), 6)))



# COUNT(CLOSE>OPEN && BANCHMARKINDEXCLOSE<BANCHMARKINDEXOPEN,50)/COUNT(BANCHMARKINDEXCLOSE<BANCHMARKINDEXOPEN,50)
def alpha_075(ctx):
  _BANCHMARKINDEXCLOSE = ctx('BANCHMARKINDEXCLOSE')
  _BANCHMARKINDEXOPEN = ctx('BANCHMARKINDEXOPEN')
  return (ctx.COUNT(np.bitwise_and((ctx('CLOSE') > ctx('OPEN')), (_BANCHMARKINDEXCLOSE < _BANCHMARKINDEXOPEN)), 50) / ctx.COUNT((_BANCHMARKINDEXCLOSE < _BANCHMARKINDEXOPEN), 50))



# STD(ABS((CLOSE/DELAY(CLOSE,1)-1))/VOLUME,20)/MEAN(ABS((CLOSE/DELAY(CLOSE,1)-1))/VOLUME,20)
def alpha_076(ctx):
  _CLOSE = ctx('CLOSE')
  _VOLUME = ctx('VOLUME')
  return (ctx.STD((ctx.ABS(((_CLOSE / ctx.DELAY(_CLOSE, 1)) - 1)) / _VOLUME), 20) / ctx.MEAN((ctx.ABS(((_CLOSE / ctx.DELAY(_CLOSE, 1)) - 1)) / _VOLUME), 20))



# MIN(RANK(DECAYLINEAR(((((HIGH + LOW) / 2) + HIGH) - (VWAP + HIGH)), 20)), RANK(DECAYLINEAR(CORR(((HIGH + LOW) / 2), MEAN(VOLUME,40), 3), 6)))
def alpha_077(ctx):
  _HIGH = ctx('HIGH')
  _LOW = ctx('LOW')
  return ctx.MIN(ctx.RANK(ctx.DECAYLINEAR(((((_HIGH + _LOW) / 2) + _HIGH) - (ctx('VWAP') + _HIGH)), 20)), ctx.RANK(ctx.DECAYLINEAR(ctx.CORR(((_HIGH + _LOW) / 2), ctx.MEAN(ctx('VOLUME'), 40), 3), 6)))



# ((HIGH+LOW+CLOSE)/3-MA((HIGH+LOW+CLOSE)/3,12))/(0.015*MEAN(ABS(CLOSE-MEAN((HIGH+LOW+CLOSE)/3,12)),12))
def alpha_078(ctx):
  _CLOSE = ctx('CLOSE')
  _HIGH = ctx('HIGH')
  _LOW = ctx('LOW')
  return ((((_HIGH + _LOW + _CLOSE) / 3) - ctx.MA(((_HIGH + _LOW + _CLOSE) / 3), 12)) / (0.015 * ctx.MEAN(ctx.ABS((_CLOSE - ctx.MEAN(((_HIGH + _LOW + _CLOSE) / 3), 12))), 12)))



# SMA(MAX(CLOSE-DELAY(CLOSE,1),0),12,1)/SMA(ABS(CLOSE-DELAY(CLOSE,1)),12,1)*100
def alpha_079(ctx):
  _CLOSE = ctx('CLOSE')
  return (ctx.SMA(ctx.MAX((_CLOSE - ctx.DELAY(_CLOSE, 1)), 0), 12, 1) / ctx.SMA(ctx.ABS((_CLOSE - ctx.DELAY(_CLOSE, 1))), 12, 1) * 100)



# (VOLUME-DELAY(VOLUME,5))/DELAY(VOLUME,5)*100
def alpha_080(ctx):
  _VOLUME = ctx('VOLUME')
  return ((_VOLUME - ctx.DELAY(_VOLUME, 5)) / ctx.DELAY(_VOLUME, 5) * 100)



# SMA(VOLUME,21,2)
def alpha_081(ctx):
  return ctx.SMA(ctx('VOLUME'), 21, 2)



# SMA((TSMAX(HIGH,6)-CLOSE)/(TSMAX(HIGH,6)-TSMIN(LOW,6))*100,20,1)
def alpha_082(ctx):
  _HIGH = ctx('HIGH')
  return ctx.SMA(((ctx.TSMAX(_HIGH, 6) - ctx('CLOSE')) / (ctx.TSMAX(_HIGH, 6) - ctx.TSMIN(ctx('LOW'), 6)) * 100), 20, 1)



# (-1 * RANK(COV(RANK(HIGH), RANK(VOLUME), 5)))
def alpha_083(ctx):
  return (-1 * ctx.RANK(ctx.COV(ctx.RANK(ctx('HIGH')), ctx.RANK(ctx('VOLUME')), 5)))



# SUM((CLOSE>DELAY(CLOSE,1)?VOLUME:(CLOSE<DELAY(CLOSE,1)?-VOLUME:0)),20)
def alpha_084(ctx):
  _CLOSE = ctx('CLOSE')
  _VOLUME = ctx('VOLUME')
  return ctx.SUM(np.where((_CLOSE > ctx.DELAY(_CLOSE, 1)), _VOLUME, np.where((_CLOSE < ctx.DELAY(_CLOSE, 1)), -_VOLUME, 0)), 20)



# (TSRANK((VOLUME / MEAN(VOLUME,20)), 20) * TSRANK((-1 * DELTA(CLOSE, 7)), 8))
def alpha_085(ctx):
  _VOLUME = ctx('VOLUME')
  return (ctx.TSRANK((_VOLUME / ctx.MEAN(_VOLUME, 20)), 20) * ctx.TSRANK((-1 * ctx.DELTA(ctx('CLOSE'), 7)), 8))



# ((0.25 < (((DELAY(CLOSE, 20) - DELAY(CLOSE, 10)) / 10) - ((DELAY(CLOSE, 10) - CLOSE) / 10))) ? (-1 * 1) : (((((DELAY(CLOSE, 20) - DELAY(CLOSE, 10)) / 10) - ((DELAY(CLOSE, 10) - CLOSE) / 10)) < 0) ? 1 : ((-1 * 1) * (CLOSE - DELAY(CLOSE, 1)))))
def alpha_086(ctx):
  _CLOSE = ctx('CLOSE')
  return np.where((0.25 < (((ctx.DELAY(_CLOSE, 20) - ctx.DELAY(_CLOSE, 10)) / 10) - ((ctx.DELAY(_CLOSE, 10) - _CLOSE) / 10))), (-1 * 1), np.where(((((ctx.DELAY(_CLOSE, 20) - ctx.DELAY(_CLOSE, 10)) / 10) - ((ctx.DELAY(_CLOSE, 10) - _CLOSE) / 10)) < 0), 1, ((-1 * 1) * (_CLOSE - ctx.DELAY(_CLOSE, 1)))))



# ((RANK(DECAYLINEAR(DELTA(VWAP, 4), 7)) + TSRANK(DECAYLINEAR(((((LOW * 0.9) + (LOW * 0.1)) - VWAP) / (OPEN - ((HIGH + LOW) / 2))), 11), 7)) * -1)
def alpha_087(ctx):
  _LOW = ctx('LOW')
  _VWAP = ctx('VWAP')
  return ((ctx.RANK(ctx.DECAYLINEAR(ctx.DELTA(_VWAP, 4), 7)) + ctx.TSRANK(ctx.DECAYLINEAR(((((_LOW * 0.9) + (_LOW * 0.1)) - _VWAP) / (ctx('OPEN') - ((ctx('HIGH') + _LOW) / 2))), 11), 7)) * -1)



# (CLOSE-DELAY(CLOSE,20))/DELAY(CLOSE,20)*100
def alpha_088(ctx):
  _CLOSE = ctx('CLOSE')
  return ((_CLOSE - ctx.DELAY(_CLOSE, 20)) / ctx.DELAY(_CLOSE, 20) * 100)



# 2*(SMA(CLOSE,13,2)-SMA(CLOSE,27,2)-SMA(SMA(CLOSE,13,2)-SMA(CLOSE,27,2),10,2))
def alpha_089(ctx):
  _CLOSE = ctx('CLOSE')
  return (2 * (ctx.SMA(_CLOSE, 13, 2) - ctx.SMA(_CLOSE, 27, 2) - ctx.SMA((ctx.SMA(_CLOSE, 13, 2) - ctx.SMA(_CLOSE, 27, 2)), 10, 2)))



# (RANK(CORR(RANK(VWAP), RANK(VOLUME), 5)) * -1)
def alpha_090(ctx):
  return (ctx.RANK(ctx.CORR(ctx.RANK(ctx('VWAP')), ctx.RANK(ctx('VOLUME')), 5)) * -1)



# ((RANK((CLOSE - MAX(CLOSE, 5)))*RANK(CORR((MEAN(VOLUME,40)), LOW, 5))) * -1)
def alpha_091(ctx):
  _CLOSE = ctx('CLOSE')
  return ((ctx.RANK((_CLOSE - ctx.MAX(_CLOSE, 5))) * ctx.RANK(ctx.CORR(ctx.MEAN(ctx('VOLUME'), 40), ctx('LOW'), 5))) * -1)



# (MAX(RANK(DECAYLINEAR(DELTA(((CLOSE * 0.35) + (VWAP *0.65)), 2), 3)), TSRANK(DECAYLINEAR(ABS(CORR((MEAN(VOLUME,180)), CLOSE, 13)), 5), 15)) * -1)
def alpha_092(ctx):
  _CLOSE = ctx('CLOSE')
  return (ctx.MAX(ctx.RANK(ctx.DECAYLINEAR(ctx.DELTA(((_CLOSE * 0.35) + (ctx('VWAP') * 0.65)), 2), 3)), ctx.TSRANK(ctx.DECAYLINEAR(ctx.ABS(ctx.CORR(ctx.MEAN(ctx('VOLUME'), 180), _CLOSE, 13)), 5), 15)) * -1)



# SUM((OPEN>=DELAY(OPEN,1)?0:MAX((OPEN-LOW),(OPEN-DELAY(OPEN,1)))),20)
def alpha_093(ctx):
  _OPEN = ctx('OPEN')
  return ctx.SUM(np.where((_OPEN >= ctx.DELAY(_OPEN, 1)), 0, ctx.MAX((_OPEN - ctx('LOW')), (_OPEN - ctx.DELAY(_OPEN, 1)))), 20)



# SUM((CLOSE>DELAY(CLOSE,1)?VOLUME:(CLOSE<DELAY(CLOSE,1)?-VOLUME:0)),30)
def alpha_094(ctx):
  _CLOSE = ctx('CLOSE')
  _VOLUME = ctx('VOLUME')
  return ctx.SUM(np.where((_CLOSE > ctx.DELAY(_CLOSE, 1)), _VOLUME, np.where((_CLOSE < ctx.DELAY(_CLOSE, 1)), -_VOLUME, 0)), 30)



# STD(AMOUNT,20)
def alpha_095(ctx):
  return ctx.STD(ctx('AMOUNT'), 20)



# SMA(SMA((CLOSE-TSMIN(LOW,9))/(TSMAX(HIGH,9)-TSMIN(LOW,9))*100,3,1),3,1)
def alpha_096(ctx):
  _LOW = ctx('LOW')
  return ctx.SMA(ctx.SMA(((ctx('CLOSE') - ctx.TSMIN(_LOW, 9)) / (ctx.TSMAX(ctx('HIGH'), 9) - ctx.TSMIN(_LOW, 9)) * 100), 3, 1), 3, 1)



# STD(VOLUME,10)
def alpha_097(ctx):
  return ctx.STD(ctx('VOLUME'), 10)



# ((((DELTA((SUM(CLOSE, 100) / 100), 100) / DELAY(CLOSE, 100)) < 0.05) || ((DELTA((SUM(CLOSE, 100) / 100), 100) / DELAY(CLOSE, 100)) == 0.05)) ? (-1 * (CLOSE - TSMIN(CLOSE, 100))) : (-1 * DELTA(CLOSE, 3)))
def alpha_098(ctx):
  _CLOSE = ctx('CLOSE')
  return np.where(np.bitwise_or(((ctx.DELTA((ctx.SUM(_CLOSE, 100) / 100), 100) / ctx.DELAY(_CLOSE, 100)) < 0.05), ((ctx.DELTA((ctx.SUM(_CLOSE, 100) / 100), 100) / ctx.DELAY(_CLOSE, 100)) == 0.05)), (-1 * (_CLOSE - ctx.TSMIN(_CLOSE, 100))), (-1 * ctx.DELTA(_CLOSE, 3)))



# (-1 * RANK(COV(RANK(CLOSE), RANK(VOLUME), 5)))
def alpha_099(ctx):
  return (-1 * ctx.RANK(ctx.COV(ctx.RANK(ctx('CLOSE')), ctx.RANK(ctx('VOLUME')), 5)))



# STD(VOLUME,20)
def alpha_100(ctx):
  return ctx.STD(ctx('VOLUME'), 20)



# ((RANK(CORR(CLOSE, SUM(MEAN(VOLUME,30), 37), 15)) < RANK(CORR(RANK(((HIGH * 0.1) + (VWAP * 0.9))), RANK(VOLUME), 11))) * -1)
def alpha_101(ctx):
  _VOLUME = ctx('VOLUME')
  return ((ctx.RANK(ctx.CORR(ctx('CLOSE'), ctx.SUM(ctx.MEAN(_VOLUME, 30), 37), 15)) < ctx.RANK(ctx.CORR(ctx.RANK(((ctx('HIGH') * 0.1) + (ctx('VWAP') * 0.9))), ctx.RANK(_VOLUME), 11))) * -1)



# SMA(MAX(VOLUME-DELAY(VOLUME,1),0),6,1)/SMA(ABS(VOLUME-DELAY(VOLUME,1)),6,1)*100
def alpha_102(ctx):
  _VOLUME = ctx('VOLUME')
  return (ctx.SMA(ctx.MAX((_VOLUME - ctx.DELAY(_VOLUME, 1)), 0), 6, 1) / ctx.SMA(ctx.ABS((_VOLUME - ctx.DELAY(_VOLUME, 1))), 6, 1) * 100)



# ((20-LOWDAY(LOW,20))/20)*100
def alpha_103(ctx):
  return (((20 - ctx.LOWDAY(ctx('LOW'), 20)) / 20) * 100)



# (-1 * (DELTA(CORR(HIGH, VOLUME, 5), 5) * RANK(STD(CLOSE, 20))))
def alpha_104(ctx):
  return (-1 * (ctx.DELTA(ctx.CORR(ctx('HIGH'), ctx('VOLUME'), 5), 5) * ctx.RANK(ctx.STD(ctx('CLOSE'), 20))))



# (-1 * CORR(RANK(OPEN), RANK(VOLUME), 10))
def alpha_105(ctx):
  return (-1 * ctx.CORR(ctx.RANK(ctx('OPEN')), ctx.RANK(ctx('VOLUME')), 10))



# CLOSE-DELAY(CLOSE,20)
def alpha_106(ctx):
  _CLOSE = ctx('CLOSE')
  return (_CLOSE - ctx.DELAY(_CLOSE, 20))



# (((-1 * RANK((OPEN - DELAY(HIGH, 1)))) * RANK((OPEN - DELAY(CLOSE, 1)))) * RANK((OPEN - DELAY(LOW, 1))))
def alpha_107(ctx):
  _OPEN = ctx('OPEN')
  return (((-1 * ctx.RANK((_OPEN - ctx.DELAY(ctx('HIGH'), 1)))) * ctx.RANK((_OPEN - ctx.DELAY(ctx('CLOSE'), 1)))) * ctx.RANK((_OPEN - ctx.DELAY(ctx('LOW'), 1))))



# ((RANK((HIGH - MIN(HIGH, 2)))^RANK(CORR((VWAP), (MEAN(VOLUME,120)), 6))) * -1)
def alpha_108(ctx):
  _HIGH = ctx('HIGH')
  return (np.power(ctx.RANK((_HIGH - ctx.MIN(_HIGH, 2))), ctx.RANK(ctx.CORR(ctx('VWAP'), ctx.MEAN(ctx('VOLUME'), 120), 6))) * -1)



# SMA(HIGH-LOW,10,2)/SMA(SMA(HIGH-LOW,10,2),10,2)
def alpha_109(ctx):
  _HIGH = ctx('HIGH')
  _LOW = ctx('LOW')
  return (ctx.SMA((_HIGH - _LOW), 10, 2) / ctx.SMA(ctx.SMA((_HIGH - _LOW), 10, 2), 10, 2))



# SUM(MAX(0,HIGH-DELAY(CLOSE,1)),20)/SUM(MAX(0,DELAY(CLOSE,1)-LOW),20)*100
def alpha_110(ctx):
  _CLOSE = ctx('CLOSE')
  return (ctx.SUM(ctx.MAX(0, (ctx('HIGH') - ctx.DELAY(_CLOSE, 1))), 20) / ctx.SUM(ctx.MAX(0, (ctx.DELAY(_CLOSE, 1) - ctx('LOW'))), 20) * 100)



# SMA(VOLUME*((CLOSE-LOW)-(HIGH-CLOSE))/(HIGH-LOW),11,2)-SMA(VOLUME*((CLOSE-LOW)-(HIGH-CLOSE))/(HIGH-LOW),4,2)
def alpha_111(ctx):
  _CLOSE = ctx('CLOSE')
  _HIGH = ctx('HIGH')
  _LOW = ctx('LOW')
  _VOLUME = ctx('VOLUME')
  return (ctx.SMA((_VOLUME * ((_CLOSE - _LOW) - (_HIGH - _CLOSE)) / (_HIGH - _LOW)), 11, 2) - ctx.SMA((_VOLUME * ((_CLOSE - _LOW) - (_HIGH - _CLOSE)) / (_HIGH - _LOW)), 4, 2))



# (SUM((CLOSE-DELAY(CLOSE,1)>0?CLOSE-DELAY(CLOSE,1):0),12)-SUM((CLOSE-DELAY(CLOSE,1)<0?ABS(CLOSE-DELAY(CLOSE,1)):0),12))/(SUM((CLOSE-DELAY(CLOSE,1)>0?CLOSE-DELAY(CLOSE,1):0),12)+SUM((CLOSE-DELAY(CLOSE,1)<0?ABS(CLOSE-DELAY(CLOSE,1)):0),12))*100
def alpha_112(ctx):
  _CLOSE = ctx('CLOSE')
  return ((ctx.SUM(np.where(((_CLOSE - ctx.DELAY(_CLOSE, 1)) > 0), (_CLOSE - ctx.DELAY(_CLOSE, 1)), 0), 12) - ctx.SUM(np.where(((_CLOSE - ctx.DELAY(_CLOSE, 1)) < 0), ctx.ABS((_CLOSE - ctx.DELAY(_CLOSE, 1))), 0), 12)) / (ctx.SUM(np.where(((_CLOSE - ctx.DELAY(_CLOSE, 1)) > 0), (_CLOSE - ctx.DELAY(_CLOSE, 1)), 0), 12) + ctx.SUM(np.where(((_CLOSE - ctx.DELAY(_CLOSE, 1)) < 0), ctx.ABS((_CLOSE - ctx.DELAY(_CLOSE, 1))), 0), 12)) * 100)



# (-1 * ((RANK((SUM(DELAY(CLOSE, 5), 20) / 20)) * CORR(CLOSE, VOLUME, 2)) * RANK(CORR(SUM(CLOSE, 5), SUM(CLOSE, 20), 2))))
def alpha_113(ctx):
  _CLOSE = ctx('CLOSE')
  return (-1 * ((ctx.RANK((ctx.SUM(ctx.DELAY(_CLOSE, 5), 20) / 20)) * ctx.CORR(_CLOSE, ctx('VOLUME'), 2)) * ctx.RANK(ctx.CORR(ctx.SUM(_CLOSE, 5), ctx.SUM(_CLOSE, 20), 2))))



# ((RANK(DELAY(((HIGH - LOW) / (SUM(CLOSE, 5) / 5)), 2)) * RANK(RANK(VOLUME))) / (((HIGH - LOW) / (SUM(CLOSE, 5) / 5)) / (VWAP - CLOSE)))
def alpha_114(ctx):
  _CLOSE = ctx('CLOSE')
  _HIGH = ctx('HIGH')
  _LOW = ctx('LOW')
  return ((ctx.RANK(ctx.DELAY(((_HIGH - _LOW) / (ctx.SUM(_CLOSE, 5) / 5)), 2)) * ctx.RANK(ctx.RANK(ctx('VOLUME')))) / (((_HIGH - _LOW) / (ctx.SUM(_CLOSE, 5) / 5)) / (ctx('VWAP') - _CLOSE)))



# (RANK(CORR(((HIGH * 0.9) + (CLOSE * 0.1)), MEAN(VOLUME,30), 10))^RANK(CORR(TSRANK(((HIGH + LOW) / 2), 4), TSRANK(VOLUME, 10), 7)))
def alpha_115(ctx):
  _HIGH = ctx('HIGH')
  _VOLUME = ctx('VOLUME')
  return np.power(ctx.RANK(ctx.CORR(((_HIGH * 0.9) + (ctx('CLOSE') * 0.1)), ctx.MEAN(_VOLUME, 30), 10)), ctx.RANK(ctx.CORR(ctx.TSRANK(((_HIGH + ctx('LOW')) / 2), 4), ctx.TSRANK(_VOLUME, 10), 7)))



# REGBETA(CLOSE,SEQUENCE,20)
def alpha_116(ctx):
  return ctx.REGBETA(ctx('CLOSE'), ctx('SEQUENCE'), 20)



# ((TSRANK(VOLUME, 32) * (1 - TSRANK(((CLOSE + HIGH) - LOW), 16))) * (1 - TSRANK(RET, 32)))
def alpha_117(ctx):
  return ((ctx.TSRANK(ctx('VOLUME'), 32) * (1 - ctx.TSRANK(((ctx('CLOSE') + ctx('HIGH')) - ctx('LOW')), 16))) * (1 - ctx.TSRANK(ctx('RET'), 32)))



# SUM(HIGH-OPEN,20)/SUM(OPEN-LOW,20)*100
def alpha_118(ctx):
  _OPEN = ctx('OPEN')
  return (ctx.SUM((ctx('HIGH') - _OPEN), 20) / ctx.SUM((_OPEN - ctx('LOW')), 20) * 100)



# (RANK(DECAYLINEAR(CORR(VWAP, SUM(MEAN(VOLUME,5), 26), 5), 7)) - RANK(DECAYLINEAR(TSRANK(MIN(CORR(RANK(OPEN), RANK(MEAN(VOLUME,15)), 21), 9), 7), 8)))
def alpha_119(ctx):
  _VOLUME = ctx('VOLUME')
  return (ctx.RANK(ctx.DECAYLINEAR(ctx.CORR(ctx('VWAP'), ctx.SUM(ctx.MEAN(_VOLUME, 5), 26), 5), 7)) - ctx.RANK(ctx.DECAYLINEAR(ctx.TSRANK(ctx.MIN(ctx.CORR(ctx.RANK(ctx('OPEN')), ctx.RANK(ctx.MEAN(_VOLUME, 15)), 21), 9), 7), 8)))



# (RANK((VWAP - CLOSE)) / RANK((VWAP + CLOSE)))
def alpha_120(ctx):
  _CLOSE = ctx('CLOSE')
  _VWAP = ctx('VWAP')
  return (ctx.RANK((_VWAP - _CLOSE)) / ctx.RANK((_VWAP + _CLOSE)))



# ((RANK((VWAP - MIN(VWAP, 12)))^TSRANK(CORR(TSRANK(VWAP, 20), TSRANK(MEAN(VOLUME,60), 2), 18), 3)) * -1)
def alpha_121(ctx):
  _VWAP = ctx('VWAP')
  return (np.power(ctx.RANK((_VWAP - ctx.MIN(_VWAP, 12))), ctx.TSRANK(ctx.CORR(ctx.TSRANK(_VWAP, 20), ctx.TSRANK(ctx.MEAN(ctx('VOLUME'), 60), 2), 18), 3)) * -1)



# (SMA(SMA(SMA(LOG(CLOSE),13,2),13,2),13,2)-DELAY(SMA(SMA(SMA(LOG(CLOSE),13,2),13,2),13,2),1))/DELAY(SMA(SMA(SMA(LOG(CLOSE),13,2),13,2),13,2),1)
def alpha_122(ctx):
  _CLOSE = ctx('CLOSE')
  return ((ctx.SMA(ctx.SMA(ctx.SMA(ctx.LOG(_CLOSE), 13, 2), 13, 2), 13, 2) - ctx.DELAY(ctx.SMA(ctx.SMA(ctx.SMA(ctx.LOG(_CLOSE), 13, 2), 13, 2), 13, 2), 1)) / ctx.DELAY(ctx.SMA(ctx.SMA(ctx.SMA(ctx.LOG(_CLOSE), 13, 2), 13, 2), 13, 2), 1))



# ((RANK(CORR(SUM(((HIGH + LOW) / 2), 20), SUM(MEAN(VOLUME,60), 20), 9)) < RANK(CORR(LOW, VOLUME, 6))) * -1)
def alpha_123(ctx):
  _LOW = ctx('LOW')
  _VOLUME = ctx('VOLUME')
  return ((ctx.RANK(ctx.CORR(ctx.SUM(((ctx('HIGH') + _LOW) / 2), 20), ctx.SUM(ctx.MEAN(_VOLUME, 60), 20), 9)) < ctx.RANK(ctx.CORR(_LOW, _VOLUME, 6))) * -1)



# (CLOSE - VWAP) / DECAYLINEAR(RANK(TSMAX(CLOSE, 30)),2)
def alpha_124(ctx):
  _CLOSE = ctx('CLOSE')
  return ((_CLOSE - ctx('VWAP')) / ctx.DECAYLINEAR(ctx.RANK(ctx.TSMAX(_CLOSE, 30)), 2))



# (RANK(DECAYLINEAR(CORR((VWAP), MEAN(VOLUME,80),17), 20)) / RANK(DECAYLINEAR(DELTA(((CLOSE * 0.5) + (VWAP * 0.5)), 3), 16)))
def alpha_125(ctx):
  _VWAP = ctx('VWAP')
  return (ctx.RANK(ctx.DECAYLINEAR(ctx.CORR(_VWAP, ctx.MEAN(ctx('VOLUME'), 80), 17), 20)) / ctx.RANK(ctx.DECAYLINEAR(ctx.DELTA(((ctx('CLOSE') * 0.5) + (_VWAP * 0.5)), 3), 16)))



# (CLOSE+HIGH+LOW)/3
def alpha_126(ctx):
  return ((ctx('CLOSE') + ctx('HIGH') + ctx('LOW')) / 3)



# (MEAN((100*(CLOSE-TSMAX(CLOSE,12))/(TSMAX(CLOSE,12)))^2, 12))^(1/2)
def alpha_127(ctx):
  _CLOSE = ctx('CLOSE')
  return np.power(ctx.MEAN(np.power((100 * (_CLOSE - ctx.TSMAX(_CLOSE, 12)) / ctx.TSMAX(_CLOSE, 12)), 2), 12), (1 / 2))



# 100-(100/(1+SUM(((HIGH+LOW+CLOSE)/3>DELAY((HIGH+LOW+CLOSE)/3,1)?(HIGH+LOW+CLOSE)/3*VOLUME:0),14)/SUM(((HIGH+LOW+CLOSE)/3<DELAY((HIGH+LOW+CLOSE)/3,1)?(HIGH+LOW+CLOSE)/3*VOLUME:0), 14)))
def alpha_128(ctx):
  _CLOSE = ctx('CLOSE')
  _HIGH = ctx('HIGH')
  _LOW = ctx('LOW')
  _VOLUME = ctx('VOLUME')
  return (100 - (100 / (1 + (ctx.SUM(np.where((((_HIGH + _LOW + _CLOSE) / 3) > ctx.DELAY(((_HIGH + _LOW + _CLOSE) / 3), 1)), ((_HIGH + _LOW + _CLOSE) / 3 * _VOLUME), 0), 14) / ctx.SUM(np.where((((_HIGH + _LOW + _CLOSE) / 3) < ctx.DELAY(((_HIGH + _LOW + _CLOSE) / 3), 1)), ((_HIGH + _LOW + _CLOSE) / 3 * _VOLUME), 0), 14)))))



# SUM((CLOSE-DELAY(CLOSE,1)<0?ABS(CLOSE-DELAY(CLOSE,1)):0),12)
def alpha_129(ctx):
  _CLOSE = ctx('CLOSE')
  return ctx.SUM(np.where(((_CLOSE - ctx.DELAY(_CLOSE, 1)) < 0), ctx.ABS((_CLOSE - ctx.DELAY(_CLOSE, 1))), 0), 12)



# (RANK(DECAYLINEAR(CORR(((HIGH + LOW) / 2), MEAN(VOLUME,40), 9), 10)) / RANK(DECAYLINEAR(CORR(RANK(VWAP), RANK(VOLUME), 7),3)))
def alpha_130(ctx):
  _VOLUME = ctx('VOLUME')
  return (ctx.RANK(ctx.DECAYLINEAR(ctx.CORR(((ctx('HIGH') + ctx('LOW')) / 2), ctx.MEAN(_VOLUME, 40), 9), 10)) / ctx.RANK(ctx.DECAYLINEAR(ctx.CORR(ctx.RANK(ctx('VWAP')), ctx.RANK(_VOLUME), 7), 3)))



# (RANK(DELTA(VWAP, 1))^TSRANK(CORR(CLOSE,MEAN(VOLUME,50), 18), 18))
def alpha_131(ctx):
  return np.power(ctx.RANK(ctx.DELTA(ctx('VWAP'), 1)), ctx.TSRANK(ctx.CORR(ctx('CLOSE'), ctx.MEAN(ctx('VOLUME'), 50), 18), 18))



# MEAN(AMOUNT,20)
def alpha_132(ctx):
  return ctx.MEAN(ctx('AMOUNT'), 20)



# ((20-HIGHDAY(HIGH,20))/20)*100-((20-LOWDAY(LOW,20))/20)*100
def alpha_133(ctx):
  return ((((20 - ctx.HIGHDAY(ctx('HIGH'), 20)) / 20) * 100) - (((20 - ctx.LOWDAY(ctx('LOW'), 20)) / 20) * 100))



# (CLOSE-DELAY(CLOSE,12))/DELAY(CLOSE,12)*VOLUME
def alpha_134(ctx):
  _CLOSE = ctx('CLOSE')
  return ((_CLOSE - ctx.DELAY(_CLOSE, 12)) / ctx.DELAY(_CLOSE, 12) * ctx('VOLUME'))



# SMA(DELAY(CLOSE/DELAY(CLOSE,20),1),20,1)
def alpha_135(ctx):
  _CLOSE = ctx('CLOSE')
  return ctx.SMA(ctx.DELAY((_CLOSE / ctx.DELAY(_CLOSE, 20)), 1), 20, 1)



# ((-1 * RANK(DELTA(RET, 3))) * CORR(OPEN, VOLUME, 10))
def alpha_136(ctx):
  return ((-1 * ctx.RANK(ctx.DELTA(ctx('RET'), 3))) * ctx.CORR(ctx('OPEN'), ctx('VOLUME'), 10))



# 16*(CLOSE-DELAY(CLOSE,1)+(CLOSE-OPEN)/2+DELAY(CLOSE,1)-DELAY(OPEN,1))/((ABS(HIGH-DELAY(CLOSE, 1))>ABS(LOW-DELAY(CLOSE,1)) && ABS(HIGH-DELAY(CLOSE,1))>ABS(HIGH-DELAY(LOW,1))?ABS(HIGH-DELAY(CLOSE,1))+ABS(LOW-DELAY(CLOSE,1))/2+ABS(DELAY(CLOSE,1)-DELAY(OPEN,1))/4:(ABS(LOW-DELAY(CLOSE,1))>ABS(HIGH-DELAY(LOW,1)) && ABS(LOW-DELAY(CLOSE,1))>ABS(HIGH-DELAY(CLOSE,1))?ABS(LOW-DELAY(CLOSE,1))+ABS(HIGH-DELAY(CLOSE,1))/2+ABS(DELAY(CLOSE,1)-DELAY(OPEN,1))/4:ABS(HIGH-DELAY(LOW,1))+ABS(DELAY(CLOSE,1)-DELAY(OPEN,1))/4)))*MAX(ABS(HIGH-DELAY(CLOSE,1)),ABS(LOW-DELAY(CLOSE,1)))
def alpha_137(ctx):
  _CLOSE = ctx('CLOSE')
  _HIGH = ctx('HIGH')
  _LOW = ctx('LOW')
  _OPEN = ctx('OPEN')
  return (16 * (_CLOSE - ctx.DELAY(_CLOSE, 1) + ((_CLOSE - _OPEN) / 2) + ctx.DELAY(_CLOSE, 1) - ctx.DELAY(_OPEN, 1)) / np.where(np.bitwise_and((ctx.ABS((_HIGH - ctx.DELAY(_CLOSE, 1))) > ctx.ABS((_LOW - ctx.DELAY(_CLOSE, 1)))), (ctx.ABS((_HIGH - ctx.DELAY(_CLOSE, 1))) > ctx.ABS((_HIGH - ctx.DELAY(_LOW, 1))))), (ctx.ABS((_HIGH - ctx.DELAY(_CLOSE, 1))) + (ctx.ABS((_LOW - ctx.DELAY(_CLOSE, 1))) / 2) + (ctx.ABS((ctx.DELAY(_CLOSE, 1) - ctx.DELAY(_OPEN, 1))) / 4)), np.where(np.bitwise_and((ctx.ABS((_LOW - ctx.DELAY(_CLOSE, 1))) > ctx.ABS((_HIGH - ctx.DELAY(_LOW, 1)))), (ctx.ABS((_LOW - ctx.DELAY(_CLOSE, 1))) > ctx.ABS((_HIGH - ctx.DELAY(_CLOSE, 1))))), (ctx.ABS((_LOW - ctx.DELAY(_CLOSE, 1))) + (ctx.ABS((_HIGH - ctx.DELAY(_CLOSE, 1))) / 2) + (ctx.ABS((ctx.DELAY(_CLOSE, 1) - ctx.DELAY(_OPEN, 1))) / 4)), (ctx.ABS((_HIGH - ctx.DELAY(_LOW, 1))) + (ctx.ABS((ctx.DELAY(_CLOSE, 1) - ctx.DELAY(_OPEN, 1))) / 4)))) * ctx.MAX(ctx.ABS((_HIGH - ctx.DELAY(_CLOSE, 1))), ctx.ABS((_LOW - ctx.DELAY(_CLOSE, 1)))))



# ((RANK(DECAYLINEAR(DELTA((((LOW * 0.7) + (VWAP *0.3))), 3), 20)) - TSRANK(DECAYLINEAR(TSRANK(CORR(TSRANK(LOW, 8), TSRANK(MEAN(VOLUME,60), 17), 5), 19), 16), 7)) * -1)
def alpha_138(ctx):
  _LOW = ctx('LOW')
  return ((ctx.RANK(ctx.DECAYLINEAR(ctx.DELTA(((_LOW * 0.7) + (ctx('VWAP') * 0.3)), 3), 20)) - ctx.TSRANK(ctx.DECAYLINEAR(ctx.TSRANK(ctx.CORR(ctx.TSRANK(_LOW, 8), ctx.TSRANK(ctx.MEAN(ctx('VOLUME'), 60), 17), 5), 19), 16), 7)) * -1)



# (-1 * CORR(OPEN, VOLUME, 10))
def alpha_139(ctx):
  return (-1 * ctx.CORR(ctx('OPEN'), ctx('VOLUME'), 10))



# MIN(RANK(DECAYLINEAR(((RANK(OPEN) + RANK(LOW)) - (RANK(HIGH) + RANK(CLOSE))), 8)), TSRANK(DECAYLINEAR(CORR(TSRANK(CLOSE, 8), TSRANK(MEAN(VOLUME,60), 20), 8), 7), 3))
def alpha_140(ctx):
  _CLOSE = ctx('CLOSE')
  return ctx.MIN(ctx.RANK(ctx.DECAYLINEAR(((ctx.RANK(ctx('OPEN')) + ctx.RANK(ctx('LOW'))) - (ctx.RANK(ctx('HIGH')) + ctx.RANK(_CLOSE))), 8)), ctx.TSRANK(ctx.DECAYLINEAR(ctx.CORR(ctx.TSRANK(_CLOSE, 8), ctx.TSRANK(ctx.MEAN(ctx('VOLUME'), 60), 20), 8), 7), 3))



# (RANK(CORR(RANK(HIGH), RANK(MEAN(VOLUME,15)), 9))* -1)
def alpha_141(ctx):
  return (ctx.RANK(ctx.CORR(ctx.RANK(ctx('HIGH')), ctx.RANK(ctx.MEAN(ctx('VOLUME'), 15)), 9)) * -1)



# (((-1 * RANK(TSRANK(CLOSE, 10))) * RANK(DELTA(DELTA(CLOSE, 1), 1))) * RANK(TSRANK((VOLUME /MEAN(VOLUME,20)), 5)))
def alpha_142(ctx):
  _CLOSE = ctx('CLOSE')
  _VOLUME = ctx('VOLUME')
  return (((-1 * ctx.RANK(ctx.TSRANK(_CLOSE, 10))) * ctx.RANK(ctx.DELTA(ctx.DELTA(_CLOSE, 1), 1))) * ctx.RANK(ctx.TSRANK((_VOLUME / ctx.MEAN(_VOLUME, 20)), 5)))



# CLOSE>DELAY(CLOSE,1)?(CLOSE-DELAY(CLOSE,1))/DELAY(CLOSE,1)*SELF:SELF
def alpha_143(ctx):
  _CLOSE = ctx('CLOSE')
  return ctx.SCAN_MUL((_CLOSE - ctx.DELAY(_CLOSE, 1)) / ctx.DELAY(_CLOSE, 1), (_CLOSE > ctx.DELAY(_CLOSE, 1)))



# SUMIF(ABS(CLOSE/DELAY(CLOSE,1)-1)/AMOUNT,20,CLOSE<DELAY(CLOSE,1))/COUNT(CLOSE<DELAY(CLOSE, 1),20)
def alpha_144(ctx):
  _CLOSE = ctx('CLOSE')
  return (ctx.SUMIF((ctx.ABS(((_CLOSE / ctx.DELAY(_CLOSE, 1)) - 1)) / ctx('AMOUNT')), 20, (_CLOSE < ctx.DELAY(_CLOSE, 1))) / ctx.COUNT((_CLOSE < ctx.DELAY(_CLOSE, 1)), 20))



# (MEAN(VOLUME,9)-MEAN(VOLUME,26))/MEAN(VOLUME,12)*100
def alpha_145(ctx):
  _VOLUME = ctx('VOLUME')
  return ((ctx.MEAN(_VOLUME, 9) - ctx.MEAN(_VOLUME, 26)) / ctx.MEAN(_VOLUME, 12) * 100)



# MEAN((CLOSE-DELAY(CLOSE,1))/DELAY(CLOSE,1)-SMA((CLOSE-DELAY(CLOSE,1))/DELAY(CLOSE,1),61,2),20)*(( CLOSE-DELAY(CLOSE,1))/DELAY(CLOSE,1)-SMA((CLOSE-DELAY(CLOSE,1))/DELAY(CLOSE,1),61,2))/SMA(((CLOSE-DELAY(CLOSE,1))/DELAY(CLOSE,1)-((CLOSE-DELAY(CLOSE,1))/DELAY(CLOSE,1)-SMA((CLOSE-DELAY(CLOSE, 1))/DELAY(CLOSE,1),61,2)))^2,60)
def alpha_146(ctx):
  _CLOSE = ctx('CLOSE')
  return (ctx.MEAN((((_CLOSE - ctx.DELAY(_CLOSE, 1)) / ctx.DELAY(_CLOSE, 1)) - ctx.SMA(((_CLOSE - ctx.DELAY(_CLOSE, 1)) / ctx.DELAY(_CLOSE, 1)), 61, 2)), 20) * (((_CLOSE - ctx.DELAY(_CLOSE, 1)) / ctx.DELAY(_CLOSE, 1)) - ctx.SMA(((_CLOSE - ctx.DELAY(_CLOSE, 1)) / ctx.DELAY(_CLOSE, 1)), 61, 2)) / ctx.SMA(np.power((((_CLOSE - ctx.DELAY(_CLOSE, 1)) / ctx.DELAY(_CLOSE, 1)) - (((_CLOSE - ctx.DELAY(_CLOSE, 1)) / ctx.DELAY(_CLOSE, 1)) - ctx.SMA(((_CLOSE - ctx.DELAY(_CLOSE, 1)) / ctx.DELAY(_CLOSE, 1)), 61, 2))), 2), 60))



# REGBETA(MEAN(CLOSE,12),SEQUENCE,12)
def alpha_147(ctx):
  return ctx.REGBETA(ctx.MEAN(ctx('CLOSE'), 12), ctx('SEQUENCE'), 12)



# ((RANK(CORR((OPEN), SUM(MEAN(VOLUME,60), 9), 6)) < RANK((OPEN - TSMIN(OPEN, 14)))) * -1)
def alpha_148(ctx):
  _OPEN = ctx('OPEN')
  return ((ctx.RANK(ctx.CORR(_OPEN, ctx.SUM(ctx.MEAN(ctx('VOLUME'), 60), 9), 6)) < ctx.RANK((_OPEN - ctx.TSMIN(_OPEN, 14)))) * -1)



# REGBETA(FILTER(CLOSE/DELAY(CLOSE,1)-1,BANCHMARKINDEXCLOSE<DELAY(BANCHMARKINDEXCLOSE,1) ),FILTER(BANCHMARKINDEXCLOSE/DELAY(BANCHMARKINDEXCLOSE,1)-1,BANCHMARKINDEXCLOSE<DELAY(BANCHMARKINDEXCLOSE,1)),252)
def alpha_149(ctx):
  _BANCHMARKINDEXCLOSE = ctx('BANCHMARKINDEXCLOSE')
  _CLOSE = ctx('CLOSE')
  return ctx.REGBETA(ctx.FILTER(((_CLOSE / ctx.DELAY(_CLOSE, 1)) - 1), (_BANCHMARKINDEXCLOSE < ctx.DELAY(_BANCHMARKINDEXCLOSE, 1))), ctx.FILTER(((_BANCHMARKINDEXCLOSE / ctx.DELAY(_BANCHMARKINDEXCLOSE, 1)) - 1), (_BANCHMARKINDEXCLOSE < ctx.DELAY(_BANCHMARKINDEXCLOSE, 1))), 252)



# (CLOSE+HIGH+LOW)/3*VOLUME
def alpha_150(ctx):
  return ((ctx('CLOSE') + ctx('HIGH') + ctx('LOW')) / 3 * ctx('VOLUME'))



# SMA(CLOSE-DELAY(CLOSE,20),20,1)
def alpha_151(ctx):
  _CLOSE = ctx('CLOSE')
  return ctx.SMA((_CLOSE - ctx.DELAY(_CLOSE, 20)), 20, 1)



# SMA(MEAN(DELAY(SMA(DELAY(CLOSE/DELAY(CLOSE,9),1),9,1),1),12)-MEAN(DELAY(SMA(DELAY(CLOSE/DELAY (CLOSE,9),1),9,1),1),26),9,1)
def alpha_152(ctx):
  _CLOSE = ctx('CLOSE')
  return ctx.SMA((ctx.MEAN(ctx.DELAY(ctx.SMA(ctx.DELAY((_CLOSE / ctx.DELAY(_CLOSE, 9)), 1), 9, 1), 1), 12) - ctx.MEAN(ctx.DELAY(ctx.SMA(ctx.DELAY((_CLOSE / ctx.DELAY(_CLOSE, 9)), 1), 9, 1), 1), 26)), 9, 1)



# (MEAN(CLOSE,3)+MEAN(CLOSE,6)+MEAN(CLOSE,12)+MEAN(CLOSE,24))/4
def alpha_153(ctx):
  _CLOSE = ctx('CLOSE')
  return ((ctx.MEAN(_CLOSE, 3) + ctx.MEAN(_CLOSE, 6) + ctx.MEAN(_CLOSE, 12) + ctx.MEAN(_CLOSE, 24)) / 4)



# (((VWAP - MIN(VWAP, 16))) < (CORR(VWAP, MEAN(VOLUME,180), 18)))
def alpha_154(ctx):
  _VWAP = ctx('VWAP')
  return ((_VWAP - ctx.MIN(_VWAP, 16)) < ctx.CORR(_VWAP, ctx.MEAN(ctx('VOLUME'), 180), 18))



# SMA(VOLUME,13,2)-SMA(VOLUME,27,2)-SMA(SMA(VOLUME,13,2)-SMA(VOLUME,27,2),10,2)
def alpha_155(ctx):
  _VOLUME = ctx('VOLUME')
  return (ctx.SMA(_VOLUME, 13, 2) - ctx.SMA(_VOLUME, 27, 2) - ctx.SMA((ctx.SMA(_VOLUME, 13, 2) - ctx.SMA(_VOLUME, 27, 2)), 10, 2))



# (MAX(RANK(DECAYLINEAR(DELTA(VWAP, 5), 3)), RANK(DECAYLINEAR(((DELTA(((OPEN * 0.15) + (LOW *0.85)), 2) / ((OPEN * 0.15) + (LOW * 0.85))) * -1), 3))) * -1)
def alpha_156(ctx):
  _LOW = ctx('LOW')
  _OPEN = ctx('OPEN')
  return (ctx.MAX(ctx.RANK(ctx.DECAYLINEAR(ctx.DELTA(ctx('VWAP'), 5), 3)), ctx.RANK(ctx.DECAYLINEAR(((ctx.DELTA(((_OPEN * 0.15) + (_LOW * 0.85)), 2) / ((_OPEN * 0.15) + (_LOW * 0.85))) * -1), 3))) * -1)



# (MIN(PROD(RANK(RANK(LOG(SUM(TSMIN(RANK(RANK((-1 * RANK(DELTA((CLOSE - 1), 5))))), 2), 1)))), 1), 5) + TSRANK(DELAY((-1 * RET), 6), 5))
def alpha_157(ctx):
  return (ctx.MIN(ctx.PROD(ctx.RANK(ctx.RANK(ctx.LOG(ctx.SUM(ctx.TSMIN(ctx.RANK(ctx.RANK((-1 * ctx.RANK(ctx.DELTA((ctx('CLOSE') - 1), 5))))), 2), 1)))), 1), 5) + ctx.TSRANK(ctx.DELAY((-1 * ctx('RET')), 6), 5))



# ((HIGH-SMA(CLOSE,15,2))-(LOW-SMA(CLOSE,15,2)))/CLOSE
def alpha_158(ctx):
  _CLOSE = ctx('CLOSE')
  return (((ctx('HIGH') - ctx.SMA(_CLOSE, 15, 2)) - (ctx('LOW') - ctx.SMA(_CLOSE, 15, 2))) / _CLOSE)



# ((CLOSE-SUM(MIN(LOW,DELAY(CLOSE,1)),6))/SUM(MAX(HIGH,DELAY(CLOSE,1))-MIN(LOW,DELAY(CLOSE,1)),6) *12*24+(CLOSE-SUM(MIN(LOW,DELAY(CLOSE,1)),12))/SUM(MAX(HIGH,DELAY(CLOSE,1))-MIN(LOW,DELAY(CLOSE,1)),12)*6*24+(CLOSE-SUM(MIN(LOW,DELAY(CLOSE,1)),24))/SUM(MAX(HIGH,DELAY(CLOSE,1))-MIN(LOW,DELAY(CLOSE,1)),24)*6*24)*100/(6*12+6*24+12*24)
def alpha_159(ctx):
  _CLOSE = ctx('CLOSE')
  _HIGH = ctx('HIGH')
  _LOW = ctx('LOW')
  return ((((_CLOSE - ctx.SUM(ctx.MIN(_LOW, ctx.DELAY(_CLOSE, 1)), 6)) / ctx.SUM((ctx.MAX(_HIGH, ctx.DELAY(_CLOSE, 1)) - ctx.MIN(_LOW, ctx.DELAY(_CLOSE, 1))), 6) * 12 * 24) + ((_CLOSE - ctx.SUM(ctx.MIN(_LOW, ctx.DELAY(_CLOSE, 1)), 12)) / ctx.SUM((ctx.MAX(_HIGH, ctx.DELAY(_CLOSE, 1)) - ctx.MIN(_LOW, ctx.DELAY(_CLOSE, 1))), 12) * 6 * 24) + ((_CLOSE - ctx.SUM(ctx.MIN(_LOW, ctx.DELAY(_CLOSE, 1)), 24)) / ctx.SUM((ctx.MAX(_HIGH, ctx.DELAY(_CLOSE, 1)) - ctx.MIN(_LOW, ctx.DELAY(_CLOSE, 1))), 24) * 6 * 24)) * 100 / ((6 * 12) + (6 * 24) + (12 * 24)))



# SMA((CLOSE<=DELAY(CLOSE,1)?STD(CLOSE,20):0),20,1)
def alpha_160(ctx):
  _CLOSE = ctx('CLOSE')
  return ctx.SMA(np.where((_CLOSE <= ctx.DELAY(_CLOSE, 1)), ctx.STD(_CLOSE, 20), 0), 20, 1)



# MEAN(MAX(MAX((HIGH-LOW),ABS(DELAY(CLOSE,1)-HIGH)),ABS(DELAY(CLOSE,1)-LOW)),12)
def alpha_161(ctx):
  _CLOSE = ctx('CLOSE')
  _HIGH = ctx('HIGH')
  _LOW = ctx('LOW')
  return ctx.MEAN(ctx.MAX(ctx.MAX((_HIGH - _LOW), ctx.ABS((ctx.DELAY(_CLOSE, 1) - _HIGH))), ctx.ABS((ctx.DELAY(_CLOSE, 1) - _LOW))), 12)



# (SMA(MAX(CLOSE-DELAY(CLOSE,1),0),12,1)/SMA(ABS(CLOSE-DELAY(CLOSE,1)),12,1)*100-MIN(SMA(MAX(CLOSE-DELAY(CLOSE,1),0),12,1)/SMA(ABS(CLOSE-DELAY(CLOSE,1)),12,1)*100,12))/(MAX(SMA(MAX(CLOSE-DELAY(CLOSE,1),0),12,1)/SMA(ABS(CLOSE-DELAY(CLOSE,1)),12,1)*100,12)-MIN(SMA(MAX(CLOSE-DELAY(CLOSE,1),0),12, 1)/SMA(ABS(CLOSE-DELAY(CLOSE,1)),12,1)*100,12))
def alpha_162(ctx):
  _CLOSE = ctx('CLOSE')
  return (((ctx.SMA(ctx.MAX((_CLOSE - ctx.DELAY(_CLOSE, 1)), 0), 12, 1) / ctx.SMA(ctx.ABS((_CLOSE - ctx.DELAY(_CLOSE, 1))), 12, 1) * 100) - ctx.MIN((ctx.SMA(ctx.MAX((_CLOSE - ctx.DELAY(_CLOSE, 1)), 0), 12, 1) / ctx.SMA(ctx.ABS((_CLOSE - ctx.DELAY(_CLOSE, 1))), 12, 1) * 100), 12)) / (ctx.MAX((ctx.SMA(ctx.MAX((_CLOSE - ctx.DELAY(_CLOSE, 1)), 0), 12, 1) / ctx.SMA(ctx.ABS((_CLOSE - ctx.DELAY(_CLOSE, 1))), 12, 1) * 100), 12) - ctx.MIN((ctx.SMA(ctx.MAX((_CLOSE - ctx.DELAY(_CLOSE, 1)), 0), 12, 1) / ctx.SMA(ctx.ABS((_CLOSE - ctx.DELAY(_CLOSE, 1))), 12, 1) * 100), 12)))



# RANK(((((-1 * RET) * MEAN(VOLUME,20)) * VWAP) * (HIGH - CLOSE)))
def alpha_163(ctx):
  return ctx.RANK(((((-1 * ctx('RET')) * ctx.MEAN(ctx('VOLUME'), 20)) * ctx('VWAP')) * (ctx('HIGH') - ctx('CLOSE'))))



# SMA((((CLOSE>DELAY(CLOSE,1))?1/(CLOSE-DELAY(CLOSE,1)):1)-MIN(((CLOSE>DELAY(CLOSE,1))?1/(CLOSE-DELAY(CLOSE,1)):1),12))/(HIGH-LOW)*100,13,2)
def alpha_164(ctx):
  _CLOSE = ctx('CLOSE')
  return ctx.SMA(((np.where((_CLOSE > ctx.DELAY(_CLOSE, 1)), (1 / (_CLOSE - ctx.DELAY(_CLOSE, 1))), 1) - ctx.MIN(np.where((_CLOSE > ctx.DELAY(_CLOSE, 1)), (1 / (_CLOSE - ctx.DELAY(_CLOSE, 1))), 1), 12)) / (ctx('HIGH') - ctx('LOW')) * 100), 13, 2)



# TSMAX(SUM(CLOSE-MEAN(CLOSE,48),48),48)-TSMIN(SUM(CLOSE-MEAN(CLOSE,48),48),48)/STD(CLOSE,48)
def alpha_165(ctx):
  _CLOSE = ctx('CLOSE')
  return (ctx.TSMAX(ctx.SUM((_CLOSE - ctx.MEAN(_CLOSE, 48)), 48), 48) - (ctx.TSMIN(ctx.SUM((_CLOSE - ctx.MEAN(_CLOSE, 48)), 48), 48) / ctx.STD(_CLOSE, 48)))



# -20* ( 20-1 ) ^1.5*SUM(CLOSE/DELAY(CLOSE,1)-1-MEAN(CLOSE/DELAY(CLOSE,1)-1,20),20)/((20-1)*(20-2)*(SUM(CLOSE/DELAY(CLOSE,1),20)^2))^1.5
def alpha_166(ctx):
  _CLOSE = ctx('CLOSE')
  return (-20 * np.power((20 - 1), 1.5) * ctx.SUM(((_CLOSE / ctx.DELAY(_CLOSE, 1)) - 1 - ctx.MEAN(((_CLOSE / ctx.DELAY(_CLOSE, 1)) - 1), 20)), 20) / np.power(((20 - 1) * (20 - 2) * np.power(ctx.SUM((_CLOSE / ctx.DELAY(_CLOSE, 1)), 20), 2)), 1.5))



# SUM((CLOSE-DELAY(CLOSE,1)>0?CLOSE-DELAY(CLOSE,1):0),12)
def alpha_167(ctx):
  _CLOSE = ctx('CLOSE')
  return ctx.SUM(np.where(((_CLOSE - ctx.DELAY(_CLOSE, 1)) > 0), (_CLOSE - ctx.DELAY(_CLOSE, 1)), 0), 12)



# (-1*VOLUME/MEAN(VOLUME,20))
def alpha_168(ctx):
  _VOLUME = ctx('VOLUME')
  return (-1 * _VOLUME / ctx.MEAN(_VOLUME, 20))



# SMA(MEAN(DELAY(SMA(CLOSE-DELAY(CLOSE,1),9,1),1),12)-MEAN(DELAY(SMA(CLOSE-DELAY(CLOSE,1),9,1),1), 26),10,1)
def alpha_169(ctx):
  _CLOSE = ctx('CLOSE')
  return ctx.SMA((ctx.MEAN(ctx.DELAY(ctx.SMA((_CLOSE - ctx.DELAY(_CLOSE, 1)), 9, 1), 1), 12) - ctx.MEAN(ctx.DELAY(ctx.SMA((_CLOSE - ctx.DELAY(_CLOSE, 1)), 9, 1), 1), 26)), 10, 1)



# ((((RANK((1 / CLOSE)) * VOLUME) / MEAN(VOLUME,20)) * ((HIGH * RANK((HIGH - CLOSE))) / (SUM(HIGH, 5) / 5))) - RANK((VWAP - DELAY(VWAP, 5))))
def alpha_170(ctx):
  _CLOSE = ctx('CLOSE')
  _HIGH = ctx('HIGH')
  _VOLUME = ctx('VOLUME')
  _VWAP = ctx('VWAP')
  return ((((ctx.RANK((1 / _CLOSE)) * _VOLUME) / ctx.MEAN(_VOLUME, 20)) * ((_HIGH * ctx.RANK((_HIGH - _CLOSE))) / (ctx.SUM(_HIGH, 5) / 5))) - ctx.RANK((_VWAP - ctx.DELAY(_VWAP, 5))))



# ((-1 * ((LOW - CLOSE) * (OPEN^5))) / ((CLOSE - HIGH) * (CLOSE^5)))
def alpha_171(ctx):
  _CLOSE = ctx('CLOSE')
  return ((-1 * ((ctx('LOW') - _CLOSE) * np.power(ctx('OPEN'), 5))) / ((_CLOSE - ctx('HIGH')) * np.power(_CLOSE, 5)))



# MEAN(ABS(SUM((LD>0 && LD>HD)?LD:0,14)*100/SUM(TR,14)-SUM((HD>0 && HD>LD)?HD:0,14)*100/SUM(TR,14))/(SUM((LD>0 && LD>HD)?LD:0,14)*100/SUM(TR,14)+SUM((HD>0 && HD>LD)?HD:0,14)*100/SUM(TR,14))*100,6)
def alpha_172(ctx):
  _HD = ctx('HD')
  _LD = ctx('LD')
  _TR = ctx('TR')
  return ctx.MEAN((ctx.ABS(((ctx.SUM(np.where(np.bitwise_and((_LD > 0), (_LD > _HD)), _LD, 0), 14) * 100 / ctx.SUM(_TR, 14)) - (ctx.SUM(np.where(np.bitwise_and((_HD > 0), (_HD > _LD)), _HD, 0), 14) * 100 / ctx.SUM(_TR, 14)))) / ((ctx.SUM(np.where(np.bitwise_and((_LD > 0), (_LD > _HD)), _LD, 0), 14) * 100 / ctx.SUM(_TR, 14)) + (ctx.SUM(np.where(np.bitwise_and((_HD > 0), (_HD > _LD)), _HD, 0), 14) * 100 / ctx.SUM(_TR, 14))) * 100), 6)



# 3*SMA(CLOSE,13,2)-2*SMA(SMA(CLOSE,13,2),13,2)+SMA(SMA(SMA(LOG(CLOSE),13,2),13,2),13,2)
def alpha_173(ctx):
  _CLOSE = ctx('CLOSE')
  return ((3 * ctx.SMA(_CLOSE, 13, 2)) - (2 * ctx.SMA(ctx.SMA(_CLOSE, 13, 2), 13, 2)) + ctx.SMA(ctx.SMA(ctx.SMA(ctx.LOG(_CLOSE), 13, 2), 13, 2), 13, 2))



# SMA((CLOSE>DELAY(CLOSE,1)?STD(CLOSE,20):0),20,1)
def alpha_174(ctx):
  _CLOSE = ctx('CLOSE')
  return ctx.SMA(np.where((_CLOSE > ctx.DELAY(_CLOSE, 1)), ctx.STD(_CLOSE, 20), 0), 20, 1)



# MEAN(MAX(MAX((HIGH-LOW),ABS(DELAY(CLOSE,1)-HIGH)),ABS(DELAY(CLOSE,1)-LOW)),6)
def alpha_175(ctx):
  _CLOSE = ctx('CLOSE')
  _HIGH = ctx('HIGH')
  _LOW = ctx('LOW')
  return ctx.MEAN(ctx.MAX(ctx.MAX((_HIGH - _LOW), ctx.ABS((ctx.DELAY(_CLOSE, 1) - _HIGH))), ctx.ABS((ctx.DELAY(_CLOSE, 1) - _LOW))), 6)



# CORR(RANK(((CLOSE - TSMIN(LOW, 12)) / (TSMAX(HIGH, 12) - TSMIN(LOW,12)))), RANK(VOLUME), 6)
def alpha_176(ctx):
  _LOW = ctx('LOW')
  return ctx.CORR(ctx.RANK(((ctx('CLOSE') - ctx.TSMIN(_LOW, 12)) / (ctx.TSMAX(ctx('HIGH'), 12) - ctx.TSMIN(_LOW, 12)))), ctx.RANK(ctx('VOLUME')), 6)



# ((20-HIGHDAY(HIGH,20))/20)*100
def alpha_177(ctx):
  return (((20 - ctx.HIGHDAY(ctx('HIGH'), 20)) / 20) * 100)



# (CLOSE-DELAY(CLOSE,1))/DELAY(CLOSE,1)*VOLUME
def alpha_178(ctx):
  _CLOSE = ctx('CLOSE')
  return ((_CLOSE - ctx.DELAY(_CLOSE, 1)) / ctx.DELAY(_CLOSE, 1) * ctx('VOLUME'))



# (RANK(CORR(VWAP, VOLUME, 4)) *RANK(CORR(RANK(LOW), RANK(MEAN(VOLUME,50)), 12)))
def alpha_179(ctx):
  _VOLUME = ctx('VOLUME')
  return (ctx.RANK(ctx.CORR(ctx('VWAP'), _VOLUME, 4)) * ctx.RANK(ctx.CORR(ctx.RANK(ctx('LOW')), ctx.RANK(ctx.MEAN(_VOLUME, 50)), 12)))



# ((MEAN(VOLUME,20) < VOLUME) ? ((-1 * TSRANK(ABS(DELTA(CLOSE, 7)), 60)) * SIGN(DELTA(CLOSE, 7))) : (-1 * VOLUME))
def alpha_180(ctx):
  _CLOSE = ctx('CLOSE')
  _VOLUME = ctx('VOLUME')
  return np.where((ctx.MEAN(_VOLUME, 20) < _VOLUME), ((-1 * ctx.TSRANK(ctx.ABS(ctx.DELTA(_CLOSE, 7)), 60)) * ctx.SIGN(ctx.DELTA(_CLOSE, 7))), (-1 * _VOLUME))



# SUM(((CLOSE/DELAY(CLOSE,1)-1)-MEAN((CLOSE/DELAY(CLOSE,1)-1),20))-(BANCHMARKINDEXCLOSE-MEAN(BANCHMARKINDEXCLOSE,20))^2,20)/SUM((BANCHMARKINDEXCLOSE-MEAN(BANCHMARKINDEXCLOSE,20))^3,20)
def alpha_181(ctx):
  _BANCHMARKINDEXCLOSE = ctx('BANCHMARKINDEXCLOSE')
  _CLOSE = ctx('CLOSE')
  return (ctx.SUM(((((_CLOSE / ctx.DELAY(_CLOSE, 1)) - 1) - ctx.MEAN(((_CLOSE / ctx.DELAY(_CLOSE, 1)) - 1), 20)) - np.power((_BANCHMARKINDEXCLOSE - ctx.MEAN(_BANCHMARKINDEXCLOSE, 20)), 2)), 20) / ctx.SUM(np.power((_BANCHMARKINDEXCLOSE - ctx.MEAN(_BANCHMARKINDEXCLOSE, 20)), 3), 20))



# COUNT((CLOSE>OPEN && BANCHMARKINDEXCLOSE>BANCHMARKINDEXOPEN) ||(CLOSE<OPEN && BANCHMARKINDEXCLOSE<BANCHMARKINDEXOPEN),20)/20
def alpha_182(ctx):
  _BANCHMARKINDEXCLOSE = ctx('BANCHMARKINDEXCLOSE')
  _BANCHMARKINDEXOPEN = ctx('BANCHMARKINDEXOPEN')
  _CLOSE = ctx('CLOSE')
  _OPEN = ctx('OPEN')
  return (ctx.COUNT(np.bitwise_or(np.bitwise_and((_CLOSE > _OPEN), (_BANCHMARKINDEXCLOSE > _BANCHMARKINDEXOPEN)), np.bitwise_and((_CLOSE < _OPEN), (_BANCHMARKINDEXCLOSE < _BANCHMARKINDEXOPEN))), 20) / 20)



# TSMAX(SUM(CLOSE-MEAN(CLOSE,24),24),24)-TSMIN(SUM(CLOSE-MEAN(CLOSE,24),24),24)/STD(CLOSE,24)
def alpha_183(ctx):
  _CLOSE = ctx('CLOSE')
  return (ctx.TSMAX(ctx.SUM((_CLOSE - ctx.MEAN(_CLOSE, 24)), 24), 24) - (ctx.TSMIN(ctx.SUM((_CLOSE - ctx.MEAN(_CLOSE, 24)), 24), 24) / ctx.STD(_CLOSE, 24)))



# (RANK(CORR(DELAY((OPEN - CLOSE), 1), CLOSE, 200)) + RANK((OPEN - CLOSE)))
def alpha_184(ctx):
  _CLOSE = ctx('CLOSE')
  _OPEN = ctx('OPEN')
  return (ctx.RANK(ctx.CORR(ctx.DELAY((_OPEN - _CLOSE), 1), _CLOSE, 200)) + ctx.RANK((_OPEN - _CLOSE)))



# RANK((-1 * ((1 - (OPEN / CLOSE))^2)))
def alpha_185(ctx):
  return ctx.RANK((-1 * np.power((1 - (ctx('OPEN') / ctx('CLOSE'))), 2)))



# (MEAN(ABS(SUM((LD>0 && LD>HD)?LD:0,14)*100/SUM(TR,14)-SUM((HD>0 && HD>LD)?HD:0,14)*100/SUM(TR,14))/(SUM((LD>0 && LD>HD)?LD:0,14)*100/SUM(TR,14)+SUM((HD>0 && HD>LD)?HD:0,14)*100/SUM(TR,14))*100,6)+DELAY(MEAN(ABS(SUM((LD>0 && LD>HD)?LD:0,14)*100/SUM(TR,14)-SUM((HD>0 && HD>LD)?HD:0,14)*100/SUM(TR,14))/(SUM((LD>0 && LD>HD)?LD:0,14)*100/SUM(TR,14)+SUM((HD>0 && HD>LD)?HD:0,14)*100/SUM(TR,14))*100,6),6))/2
def alpha_186(ctx):
  _HD = ctx('HD')
  _LD = ctx('LD')
  _TR = ctx('TR')
  return ((ctx.MEAN((ctx.ABS(((ctx.SUM(np.where(np.bitwise_and((_LD > 0), (_LD > _HD)), _LD, 0), 14) * 100 / ctx.SUM(_TR, 14)) - (ctx.SUM(np.where(np.bitwise_and((_HD > 0), (_HD > _LD)), _HD, 0), 14) * 100 / ctx.SUM(_TR, 14)))) / ((ctx.SUM(np.where(np.bitwise_and((_LD > 0), (_LD > _HD)), _LD, 0), 14) * 100 / ctx.SUM(_TR, 14)) + (ctx.SUM(np.where(np.bitwise_and((_HD > 0), (_HD > _LD)), _HD, 0), 14) * 100 / ctx.SUM(_TR, 14))) * 100), 6) + ctx.DELAY(ctx.MEAN((ctx.ABS(((ctx.SUM(np.where(np.bitwise_and((_LD > 0), (_LD > _HD)), _LD, 0), 14) * 100 / ctx.SUM(_TR, 14)) - (ctx.SUM(np.where(np.bitwise_and((_HD > 0), (_HD > _LD)), _HD, 0), 14) * 100 / ctx.SUM(_TR, 14)))) / ((ctx.SUM(np.where(np.bitwise_and((_LD > 0), (_LD > _HD)), _LD, 0), 14) * 100 / ctx.SUM(_TR, 14)) + (ctx.SUM(np.where(np.bitwise_and((_HD > 0), (_HD > _LD)), _HD, 0), 14) * 100 / ctx.SUM(_TR, 14))) * 100), 6), 6)) / 2)



# SUM((OPEN<=DELAY(OPEN,1)?0:MAX((HIGH-OPEN),(OPEN-DELAY(OPEN,1)))),20)
def alpha_187(ctx):
  _OPEN = ctx('OPEN')
  return ctx.SUM(np.where((_OPEN <= ctx.DELAY(_OPEN, 1)), 0, ctx.MAX((ctx('HIGH') - _OPEN), (_OPEN - ctx.DELAY(_OPEN, 1)))), 20)



# ((HIGH - LOW - SMA(HIGH-LOW,11,2))/SMA(HIGH-LOW,11,2))*100
def alpha_188(ctx):
  _HIGH = ctx('HIGH')
  _LOW = ctx('LOW')
  return (((_HIGH - _LOW - ctx.SMA((_HIGH - _LOW), 11, 2)) / ctx.SMA((_HIGH - _LOW), 11, 2)) * 100)



# MEAN(ABS(CLOSE-MEAN(CLOSE,6)),6)
def alpha_189(ctx):
  _CLOSE = ctx('CLOSE')
  return ctx.MEAN(ctx.ABS((_CLOSE - ctx.MEAN(_CLOSE, 6))), 6)



# LOG((COUNT(CLOSE/DELAY(CLOSE,1)-1>((CLOSE/DELAY(CLOSE,19))^(1/20)-1),20)-1)*(SUMIF(((CLOSE/DELAY(CLOSE,1)-1-(CLOSE/DELAY(CLOSE,19))^(1/20)-1))^2,20,CLOSE/DELAY(CLOSE,1)-1<(CLOSE/DELAY(CLOSE,19))^(1/20)-1))/((COUNT((CLOSE/DELAY(CLOSE,1)-1<(CLOSE/DELAY(CLOSE,19))^(1/20)-1),20))*(SUMIF((CLOSE/DELAY(CLOSE,1)-1-((CLOSE/DELAY(CLOSE,19))^(1/20)-1))^2,20,CLOSE/DELAY(CLOSE,1)-1>(CLOSE/DELAY(CLOSE,19))^(1/20)-1))))
def alpha_190(ctx):
  _CLOSE = ctx('CLOSE')
  return ctx.LOG(((ctx.COUNT((((_CLOSE / ctx.DELAY(_CLOSE, 1)) - 1) > (np.power((_CLOSE / ctx.DELAY(_CLOSE, 19)), (1 / 20)) - 1)), 20) - 1) * ctx.SUMIF(np.power(((_CLOSE / ctx.DELAY(_CLOSE, 1)) - 1 - np.power((_CLOSE / ctx.DELAY(_CLOSE, 19)), (1 / 20)) - 1), 2), 20, (((_CLOSE / ctx.DELAY(_CLOSE, 1)) - 1) < (np.power((_CLOSE / ctx.DELAY(_CLOSE, 19)), (1 / 20)) - 1))) / (ctx.COUNT((((_CLOSE / ctx.DELAY(_CLOSE, 1)) - 1) < (np.power((_CLOSE / ctx.DELAY(_CLOSE, 19)), (1 / 20)) - 1)), 20) * ctx.SUMIF(np.power(((_CLOSE / ctx.DELAY(_CLOSE, 1)) - 1 - (np.power((_CLOSE / ctx.DELAY(_CLOSE, 19)), (1 / 20)) - 1)), 2), 20, (((_CLOSE / ctx.DELAY(_CLOSE, 1)) - 1) > (np.power((_CLOSE / ctx.DELAY(_CLOSE, 19)), (1 / 20)) - 1))))))



# ((CORR(MEAN(VOLUME,20), LOW, 5) + ((HIGH + LOW) / 2)) - CLOSE)
def alpha_191(ctx):
  _LOW = ctx('LOW')
  return ((ctx.CORR(ctx.MEAN(ctx('VOLUME'), 20), _LOW, 5) + ((ctx('HIGH') + _LOW) / 2)) - ctx('CLOSE'))



