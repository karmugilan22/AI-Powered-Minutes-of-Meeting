import wave
import struct

f='data/audio/a9c61462-e390-4200-b4b7-1ef611676f66.wav'
try:
    with wave.open(f,'rb') as w:
        n=w.getnframes()
        rate=w.getframerate()
        nch=w.getnchannels()
        sampwidth=w.getsampwidth()
        frames=w.readframes(min(n,100000))
        maxv=0
        if sampwidth==2 and frames:
            fmt='<{}h'.format(len(frames)//2)
            vals=struct.unpack(fmt,frames)
            maxv=max(abs(v) for v in vals) if vals else 0
        print(n,rate,nch,sampwidth,maxv)
except Exception as e:
    print('ERR', e)
