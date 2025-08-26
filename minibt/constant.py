
from .other import Meta


class MaType(int, metaclass=Meta):
    """### 均线类型
    attrs:
    --
    >>> SMA = 0
        EMA = 1
        WMA = 2
        DEMA = 3
        TEMA = 4
        TRIMA = 5
        KAMA = 6
        MAMA = 7
        T3 = 8"""
    SMA = 0
    EMA = 1
    WMA = 2
    DEMA = 3
    TEMA = 4
    TRIMA = 5
    KAMA = 6
    MAMA = 7
    T3 = 8


class Model(str, metaclass=Meta):
    """### model (str): 多线程库
    >>> ['dask','joblib','sklearn','multiprocessing']."""
    joblib = "joblib"
    dask = "dask"
    sklearn = "sklearn"
    multiprocessing = "multiprocessing"


class LineDash(str, metaclass=Meta):
    """### 线型
    >>> 'solid','dashed','dotted','dotdash','dashdot','vbar'"""
    solid = 'solid'
    dashed = 'dashed'
    dotted = 'dotted'
    dotdash = 'dotdash'
    dashdot = 'dashdot'
    vbar = 'vbar'


class Markers(str, metaclass=Meta):
    """### 标记
    >>> "*"  : "asterisk",
        "+"  : "cross",
        "o"  : "circle",
        "o+" : "circle_cross",
        "o." : "circle_dot",
        "ox" : "circle_x",
        "oy" : "circle_y",
        "-"  : "dash",
        "."  : "dot",
        "v"  : "inverted_triangle",
        "^"  : "triangle",
        "^." : "triangle_dot'"""
    asterisk = "asterisk"
    cross = "cross"
    circle = "circle"
    circle_cross = "circle_cross"
    circle_dot = "circle_dot"
    circle_x = "circle_x"
    circle_y = "circle_y"
    dash = "dash"
    dot = "dot"
    inverted_triangle = "inverted_triangle"
    triangle = "triangle"
    triangle_dot = "triangle_dot"


class Colors(str, metaclass=Meta):
    """### 颜色
    >>> ["aliceblue", "antiquewhite", "aqua", "aquamarine", "azure",
        "beige", "bisque", "black", "blanchedalmond", "blue",
        "blueviolet", "brown", "burlywood", "cadetblue", "chartreuse",
        "chocolate", "coral", "cornflowerblue", "cornsilk", "crimson",
        "cyan", "darkblue", "darkcyan", "darkgoldenrod", "darkgray",
        "darkgreen", "darkgrey", "darkkhaki", "darkmagenta",
        "darkolivegreen", "darkorange", "darkorchid", "darkred",
        "darksalmon", "darkseagreen", "darkslateblue", "darkslategray",
        "darkslategrey", "darkturquoise", "darkviolet", "deeppink",
        "deepskyblue", "dimgray", "dimgrey", "dodgerblue", "firebrick",
        "floralwhite", "forestgreen", "fuchsia", "gainsboro", "ghostwhite",
        "gold", "goldenrod", "gray", "green", "greenyellow", "grey",
        "honeydew", "hotpink", "indianred", "indigo", "ivory", "khaki",
        "lavender", "lavenderblush", "lawngreen", "lemonchiffon",
        "lightblue", "lightcoral", "lightcyan", "lightgoldenrodyellow",
        "lightgray", "lightgreen", "lightgrey", "lightpink", "lightsalmon",
        "lightseagreen", "lightskyblue", "lightslategray",
        "lightslategrey", "lightsteelblue", "lightyellow",
        "lime", "limegreen", "linen", "magenta", "maroon",
        "mediumaquamarine", "mediumblue", "mediumorchid",
        "mediumpurple", "mediumseagreen", "mediumslateblue",
        "mediumspringgreen", "mediumturquoise", "mediumvioletred",
        "midnightblue", "mintcream", "mistyrose", "moccasin", "navajowhite",
        "navy", "oldlace", "olive", "olivedrab", "orange", "orangered",
        "orchid", "palegoldenrod", "palegreen", "paleturquoise",
        "palevioletred", "papayawhip", "peachpuff", "peru", "pink",
        "plum", "powderblue", "purple", "rebeccapurple", "red",
        "rosybrown", "royalblue", "saddlebrown", "salmon", "sandybrown",
        "seagreen", "seashell", "sienna", "silver", "skyblue", "slateblue",
        "slategray", "slategrey", "snow", "springgreen", "steelblue",
        "tan", "teal", "thistle", "tomato", "turquoise", "violet",
        "wheat", "white", "whitesmoke", "yellow", "yellowgreen",]
    """
    aliceblue = "aliceblue"
    antiquewhite = "antiquewhite"
    aqua = "aqua"
    aquamarine = "aquamarine"
    azure = "azure"
    beige = "beige"
    bisque = "bisque"
    black = "black"
    blanchedalmond = "blanchedalmond"
    blue = "blue"
    blueviolet = "blueviolet"
    brown = "brown"
    burlywood = "burlywood"
    cadetblue = "cadetblue"
    chartreuse = "chartreuse"
    chocolate = "chocolate"
    coral = "coral"
    cornflowerblue = "cornflowerblue"
    cornsilk = "cornsilk"
    crimson = "crimson"
    cyan = "cyan"
    darkblue = "darkblue"
    darkcyan = "darkcyan"
    darkgoldenrod = "darkgoldenrod"
    darkgray = "darkgray"
    darkgreen = "darkgreen"
    darkgrey = "darkgrey"
    darkkhaki = "darkkhaki"
    darkmagenta = "darkmagenta"
    darkolivegreen = "darkolivegreen"
    darkorange = "darkorange"
    darkorchid = "darkorchid"
    darkred = "darkred"
    darksalmon = "darksalmon"
    darkseagreen = "darkseagreen"
    darkslateblue = "darkslateblue"
    darkslategray = "darkslategray"
    darkslategrey = "darkslategrey"
    darkturquoise = "darkturquoise"
    darkviolet = "darkviolet"
    deeppink = "deeppink"
    deepskyblue = "deepskyblue"
    dimgray = "dimgray"
    dimgrey = "dimgrey"
    dodgerblue = "dodgerblue"
    firebrick = "firebrick"
    floralwhite = "floralwhite"
    forestgreen = "forestgreen"
    fuchsia = "fuchsia"
    gainsboro = "gainsboro"
    ghostwhite = "ghostwhite"
    gold = "gold"
    goldenrod = "goldenrod"
    gray = "gray"
    green = "green"
    greenyellow = "greenyellow"
    grey = "grey"
    honeydew = "honeydew"
    hotpink = "hotpink"
    indianred = "indianred"
    indigo = "indigo"
    ivory = "ivory"
    khaki = "khaki"
    lavender = "lavender"
    lavenderblush = "lavenderblush"
    lawngreen = "lawngreen"
    lemonchiffon = "lemonchiffon"
    lightblue = "lightblue"
    lightcoral = "lightcoral"
    lightcyan = "lightcyan"
    lightgoldenrodyellow = "lightgoldenrodyellow"
    lightgray = "lightgray"
    lightgreen = "lightgreen"
    lightgrey = "lightgrey"
    lightpink = "lightpink"
    lightsalmon = "lightsalmon"
    lightseagreen = "lightseagreen"
    lightskyblue = "lightskyblue"
    lightslategray = "lightslategray"
    lightslategrey = "lightslategrey"
    lightsteelblue = "lightsteelblue"
    lightyellow = "lightyellow"
    lime = "lime"
    limegreen = "limegreen"
    linen = "linen"
    magenta = "magenta"
    maroon = "maroon"
    mediumaquamarine = "mediumaquamarine"
    mediumblue = "mediumblue"
    mediumorchid = "mediumorchid"
    mediumpurple = "mediumpurple"
    mediumseagreen = "mediumseagreen"
    mediumslateblue = "mediumslateblue"
    mediumspringgreen = "mediumspringgreen"
    mediumturquoise = "mediumturquoise"
    mediumvioletred = "mediumvioletred"
    midnightblue = "midnightblue"
    mintcream = "mintcream"
    mistyrose = "mistyrose"
    moccasin = "moccasin"
    navajowhite = "navajowhite"
    navy = "navy"
    oldlace = "oldlace"
    olive = "olive"
    olivedrab = "olivedrab"
    orange = "orange"
    orangered = "orangered"
    orchid = "orchid"
    palegoldenrod = "palegoldenrod"
    palegreen = "palegreen"
    paleturquoise = "paleturquoise"
    palevioletred = "palevioletred"
    papayawhip = "papayawhip"
    peachpuff = "peachpuff"
    peru = "peru"
    pink = "pink"
    plum = "plum"
    powderblue = "powderblue"
    purple = "purple"
    rebeccapurple = "rebeccapurple"
    red = "red"
    rosybrown = "rosybrown"
    royalblue = "royalblue"
    saddlebrown = "saddlebrown"
    salmon = "salmon"
    sandybrown = "sandybrown"
    seagreen = "seagreen"
    seashell = "seashell"
    sienna = "sienna"
    silver = "silver"
    skyblue = "skyblue"
    slateblue = "slateblue"
    slategray = "slategray"
    slategrey = "slategrey"
    snow = "snow"
    springgreen = "springgreen"
    steelblue = "steelblue"
    tan = "tan"
    teal = "teal"
    thistle = "thistle"
    tomato = "tomato"
    turquoise = "turquoise"
    violet = "violet"
    wheat = "wheat"
    white = "white"
    whitesmoke = "whitesmoke"
    yellow = "yellow"
    yellowgreen = "yellowgreen"
    RGB666666 = "#666666"
