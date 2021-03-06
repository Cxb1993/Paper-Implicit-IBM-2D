import sys
sys.path.append("c:\HeartValve")
sys.path.append("c:\HeartValve\IB_c\Release")
from scipy.linalg import eig as Eig
from pylab import *
from numpy import *
from numpy.fft import fft2, ifft2, fft as FFT, ifft as IFFT, rfft
from IB_Methods import *
import IB_c
from ValveSetup import *
from scipy import sparse
import time
import random
import math
#show()


def GetEig(D, e1, e2, w):
    w -= dot(w,e1) * e1 / dot(e1,e1)
    w -= dot(w,e2) * e2 / dot(e2,e2)

    for i in range(3):
        w = linalg.solve(D,w)
        
        w -= dot(w,e1) * e1 / dot(e1,e1)
        w -= dot(w,e2) * e2 / dot(e2,e2)
        w /= dot(w,w)**.5        

    return w


def FluidSolve (u, v, ux, vx, uy, vy, X, Y, Fx, Fy):
    IB_c.CentralDerivative_x (N, M, h, u, ux)
    IB_c.CentralDerivative_x (N, M, h, v, vx)
    IB_c.CentralDerivative_y (N, M, h, u, uy)
    IB_c.CentralDerivative_y (N, M, h, v, vy)

    fx, fy = ForceToGrid (N, M, h, Nb, hb, Old_X, Old_Y, Fx, Fy)
    
    fx, fy = ExplicitTerms (dt, u, v, ux, uy, vx, vy, fx, fy)
#    fx += dt * Current * ones((N,M),float64)

    fx = fft2(fx)
    fy = fft2(fy)

    P = Solve_P_Hat (dt, WideLambda, DxSymbol, DySymbol, fx, fy)
    P[0,0] = 0.   

    u, v = Solve_uv_Hat (dt, ShortLambda, DxSymbol, DySymbol, P, fx, fy)

    u = ifft2(u).real
    v = ifft2(v).real

    return VelToFiber (N, M, h, Nb, hb, 1., X, Y, u, v)


def dF(i, Nb, X, Y, Links, Tethers):
    _i = i % Nb
    
    _dA = zeros(2*Nb,float64)
    for link in Links:
        a, b, s, L = link
        if a == _i or b == _i:
            l = ((X[b] - X[a])**2 + (Y[b] - Y[a])**2)**.5

            if a == _i: j = b
            else: j = a

            if i < Nb:
                d = s * (-1. + L * (1./l - (X[b] - X[a])**2 / l**3))
                _dA[i] += d
                _dA[j] -= d

                d = -s * L * (X[j] - X[i]) * (Y[j] - Y[i]) / l**3
                _dA[i+Nb] += d
                _dA[j+Nb] -= d
            else:
                d = s * (-1. + L * (1./l - (Y[b] - Y[a])**2 / l**3))
                _dA[i] += d
                _dA[j+Nb] -= d

                d = -s * L * (X[j] - X[_i]) * (Y[j] - Y[_i]) / l**3
                _dA[_i] += d
                _dA[j] -= d


    for tether in Tethers:
        a, _x, s = tether
        if a == _i:
            _dA[i] += -s

    return _dA



def FiberForce (Nb, X, Y, Xss, Yss, Links, Tethers):
    for i in range(Nb):
        Xss[i] = Yss[i] = 0.
    
    for A in Links:
        a, b, s, L = A

        l = ((X[b] - X[a])**2 + (Y[b] - Y[a])**2)**.5
        tx, ty = (X[b] - X[a]) / l, (Y[b] - Y[a]) / l

        Xss[a] += s * (X[b] - X[a] - L * tx)
        Yss[a] += s * (Y[b] - Y[a] - L * ty)
        Xss[b] -= s * (X[b] - X[a] - L * tx)
        Yss[b] -= s * (Y[b] - Y[a] - L * ty)

    for A in Tethers:
        a, _x, s = A
        x, y = _x

        Xss[a] += s * (x - X[a])
        Yss[a] += s * (y - Y[a])
#        Xss[a] += -s*X[a]
#        Yss[a] += -s*Y[a]

    return Xss, Yss
    
def Jacobian(z, Nb, Links, Tethers):
    D = zeros((2*Nb,2*Nb),float64)
    for k in range(2*Nb):
        _dF = dF(k, Nb, z[0:Nb], z[Nb:2*Nb], Links, Tethers)
        D[k,:] = _dF
    D = sparse.csc_matrix(D)
    return D
 


def _FiberForce (Nb, x, Xss, Yss, Links, Tethers):
    Xss, Yss = FiberForce (Nb, x[:Nb], x[Nb:], Xss, Yss, Links, Tethers)
    f = 1. * x
    f[:Nb], f[Nb:] = 1.*Xss, 1.*Yss
    return f
  


Domain_x, Domain_y = 2., 1.
h = .003
#h =.0015
N, M = int(Domain_x / h), int(Domain_y / h)
Domain_x, Domain_y = N * h, M * h
print "N, M =", N, M
dt = .01
T = 5.
CurT = 0

_s = 5000000000.
Current = 100.

WideLambda = zeros((N,M),float64)
ShortLambda = zeros((N,M),float64)
IB_c.InitWideLaplacian(N, M, h, WideLambda)
IB_c.InitShortLaplacian(N, M, h, ShortLambda)
DxSymbol = InitDxSymbol(N, M, h)
DySymbol = InitDySymbol(N, M, h)

_h = h
_N, _M = int(Domain_x/ _h), int(Domain_y / _h)
UField, VField, UField2, VField2 = InitVelField(_N, _M, _h, h, dt)

print UField[0,0],VField2[0,0]
clf()
clf(); imshow(UField); colorbar(); #show(); raw_input("")
clf(); imshow(VField2); colorbar(); #show(); raw_input("")

X, Y, Links, Tethers, Parts = ConstructValve (_s, 0., Domain_x, 0., Domain_y, .025, True)#.01)
s2, __I, _x2, _y2, Links2, Tethers2, Parts2 = ReduceValve(_s, X, Y, Links, Tethers, Parts)
Nb2 = len(_x2)


_II = 1. * __I

_n, _m = _II.shape
__II = zeros((2*_n,2*_m),float64)
__II[:_n,:_m] = 1. * _II
__II[_n:,_m:] = 1. * _II
II = [sparse.csc_matrix(__II)]
s3, _x3, _y3, Links3, Tethers3, Parts3 = s2, _x2, _y2, Links2, Tethers2, Parts2
while len(_II) > 10:
    s3, _II, _x3, _y3, Links3, Tethers3, Parts3 = ReduceValve(s3, _x3, _y3, Links3, Tethers3, Parts3)
    _n, _m = _II.shape
    __II = zeros((2*_n,2*_m),float64)
    __II[:_n,:_m] = 1. * _II
    __II[_n:,_m:] = 1. * _II
    II.append(sparse.csc_matrix(__II))


Nb = len(X)
print "Nb =", Nb
hb = 1. / Nb
hb = 1.

i1, i2 = Parts[3][1], Parts[3][2]
Tethers.append((i1,(X[i1],Y[i1]),_s))
Tethers.append((i2,(X[i2],Y[i2]),_s))


Xs = zeros(Nb, float64)
Ys = zeros(Nb, float64)
Xss = zeros(Nb, float64)
Yss = zeros(Nb, float64)
u = zeros((N,M), float64)
v = zeros((N,M), float64)
ux = zeros((N,M), float64)
vx = zeros((N,M), float64)
uy = zeros((N,M), float64)
vy = zeros((N,M), float64)
fx = zeros((N,M), float64)
fy = zeros((N,M), float64)

Xss2 = zeros(Nb2, float64)
Yss2 = zeros(Nb2, float64)


PlotValve (X, Y, Links)


A = zeros((2*Nb,2*Nb), float64)


Old_X, Old_Y = 1. * X, 1. * Y

b = zeros(2*Nb,float64)
count = 0
while CurT < T:
    print "Time:", CurT
    CurT += dt

    Predict_X, Predict_Y = X + .5 * (X - Old_X), Y + .25 * (Y - Old_Y)

    Old_u, Old_v = 1. * u, 1. * v
    Old_X, Old_Y = 1. * X, 1. * Y

    IB_c.CentralDerivative_x (N, M, h, u, ux)
    IB_c.CentralDerivative_x (N, M, h, v, vx)
    IB_c.CentralDerivative_y (N, M, h, u, uy)
    IB_c.CentralDerivative_y (N, M, h, v, vy)

    fx, fy = ExplicitTerms (dt, u, v, ux, uy, vx, vy, 0., 0.)
    fx += dt * Current * ones((N,M),float64)

    fx = fft2(fx)
    fy = fft2(fy)

    P = Solve_P_Hat (dt, WideLambda, DxSymbol, DySymbol, fx, fy)
    P[0,0] = 0.   

    u, v = Solve_uv_Hat (dt, ShortLambda, DxSymbol, DySymbol, P, fx, fy)
    u = ifft2(u).real
    v = ifft2(v).real

    Xvel, Yvel = VelToFiber (N, M, h, Nb, hb, 1., X, Y, u, v)





    A = zeros((2*Nb,2*Nb),float64)
    IB_c.ComputeMatrix (X, Y, _N, _M, Nb, _h, hb, UField, VField, UField2, VField2, A, -1)#, band = Nb/8+1)

    __A = [dt*A]
    for i in range(len(II)):
        print i
        __A.append( array(dot(transpose(II[i].todense()),dot(__A[i],II[i].todense()))) )

  
    for i in range(Nb):
        b[i] = X[i] + dt * Xvel[i]
        b[i+Nb] = Y[i] + dt * Yvel[i]


    x = zeros(2*Nb,float64)
    x[0:Nb], x[Nb:2*Nb] = 1. * X, 1. * Y


    i1, i2 = Parts[3][1], Parts[3][2]


    I = zeros((2*Nb-4,2*Nb),float64)
    I[:i1,:i1] = identity(i1)
    I[i1:i2-1,i1+1:i2] = identity(i2-i1-1)
    I[i2-1:Nb-2,i2+1:Nb] = identity(Nb-i2-1)
    I[Nb-2:,Nb:] = 1. * I[:Nb-2,:Nb]

##    f = _FiberForce (Nb, x, Xss, Yss, Links, Tethers)
##    _x = x + dt*dot(A,f)
##    x[i1], x[i1+Nb], x[i2], x[i2+Nb] = _x[i1], _x[i1+Nb], _x[i2], _x[i2+Nb]

    Tethers = Tethers[:len(Tethers)-2]

    clf()
    MaxRes = 1.
    its = 0
    while MaxRes > .000001 and its < 200:
    #while its < 100:
        print its
        #if MaxRes < .000001:
        if its % 30 == 0:
            print "update"
##            Tethers = Tethers[:len(Tethers)-2]
            print len(Tethers)
##            f = _FiberForce (Nb, x, Xss, Yss, Links, Tethers)
##            r = dot(I,b + dot(dt*A,f) - x)
##            clf(); plot(r);raw_input("")
            
            
            f = _FiberForce (Nb, x, Xss, Yss, Links, Tethers)
            _x = .5 * x + .5 * (b + dt*dot(A,f))
##            Tethers.append ((i1,(_x[i1],_x[i1+Nb]),5*_s))
##            Tethers.append ((i2,(_x[i2],_x[i2+Nb]),5*_s))

##            f[i1] = 0#(f[i1+1]+f[i1-1])/2.
##            f[i1+Nb] = 0#(f[i1+1+Nb]+f[i1-1+Nb])/2.
##            f[i2] = 0#(f[i2+1]+f[i2-1])/2.
##            f[i2+Nb] = 0#(f[i2+1+Nb]+f[i2-1+Nb])/2.
            x[i1], x[i1+Nb], x[i2], x[i2+Nb] = _x[i1], _x[i1+Nb], _x[i2], _x[i2+Nb]

            print "new x", _x[i1],_x[i1+Nb], _x[i2],_x[i2+Nb]
            clf(); scatter(x[:Nb],x[Nb:]); raw_input("")

        its += 1
        D = Jacobian(x, Nb, Links, Tethers)
        D = array(D.todense())

        F = linalg.solve(dt*A, x-b)
        _f = _FiberForce (Nb, x, Xss, Yss, Links, Tethers)
        f = F - _f

        clf()
        plot(f)
        raw_input("")

#        y = linalg.solve(dot(I,dot(D,I.T)),dot(I,f))
        K = dot(D,I.T)
        y = .5*linalg.solve(dot(K.T,K), dot(K.T,f))
        x += dot(I.T,y)


##        y = linalg.solve(D,f)
##        x += y

        

        print "y"
        clf(); plot(y); raw_input("")

        f = _FiberForce (Nb, x, Xss, Yss, Links, Tethers)
        r = dot(I,b + dot(dt*A,f) - x)

        clf(); plot(F,c='r'); plot(f,'b');raw_input("")

        print "Residual!"
        #clf(); plot(r); raw_input("")
        MaxRes = max(list(abs(r)))



    f = _FiberForce (Nb, x, Xss, Yss, Links, Tethers)
    r = b + dot(dt*A,f) - x

    print "Residual:", max(list(abs(r)))
    print "Residual:", max(list(abs(dot(I,r))))        



    X, Y = 1.*x[0:Nb], 1.*x[Nb:2*Nb]



    u, v = 1. * Old_u, 1. * Old_v
    IB_c.CentralDerivative_x (N, M, h, u, ux)
    IB_c.CentralDerivative_x (N, M, h, v, vx)
    IB_c.CentralDerivative_y (N, M, h, u, uy)
    IB_c.CentralDerivative_y (N, M, h, v, vy)

    Xss, Yss = FiberForce (Nb, X, Y, Xss, Yss, Links, Tethers)   

#    f = linalg.solve(dt*A,x-b)
#    Xss, Yss = 1.*f[:Nb], 1.*f[Nb:]

    fx, fy = ForceToGrid (N, M, h, Nb, hb, Old_X, Old_Y, Xss, Yss)
    
    fx, fy = ExplicitTerms (dt, u, v, ux, uy, vx, vy, fx, fy)
    fx += dt * Current * ones((N,M),float64)

    fx = fft2(fx)
    fy = fft2(fy)

    P = Solve_P_Hat (dt, WideLambda, DxSymbol, DySymbol, fx, fy)
    P[0,0] = 0.   

    u, v = Solve_uv_Hat (dt, ShortLambda, DxSymbol, DySymbol, P, fx, fy)

    u = ifft2(u).real
    v = ifft2(v).real

    Xvel, Yvel = VelToFiber (N, M, h, Nb, hb, 1., Old_X, Old_Y, u, v)
    _X, _Y = Old_X + dt*Xvel, Old_Y + dt*Yvel
   
    count += 1
    if count % 1 == 0:
        P = ifft2(P).real
        clf()
        imshow(P)
        scatter(M*Y,N*X/2)
        scatter(_X,_Y,c='r')
        quiver(M*Y,N*X/2,Y-Old_Y,-(X-Old_X))
        #show()
    raw_input("")
