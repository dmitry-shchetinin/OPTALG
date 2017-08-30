#****************************************************#
# This file is part of OPTALG.                       #
#                                                    #
# Copyright (c) 2015, Tomas Tinoco De Rubira.        #
#                                                    #
# OPTALG is released under the BSD 2-clause license. #
#****************************************************#

from __future__ import print_function
import numpy as np
from .opt_solver_error import *
from .opt_solver import OptSolver
from .problem import cast_problem
from optalg.lin_solver import new_linsolver
from scipy.sparse import bmat,triu,eye,spdiags,coo_matrix

class OptSolverINLP(OptSolver):
    """
    Interior-point non-linear programming solver.
    """
    
    # Solver parameters
    parameters = {'tol': 1e-4,            # Optimality tolerance
                  'maxiter': 300,         # Max iterations
                  'sigma': 0.1,           # Factor for increasing subproblem solution accuracy
                  'eps': 1e-3,            # Boundary proximity factor 
                  'eps_cold': 1e-2,       # Boundary proximity factor (cold start)
                  'linsolver': 'default', # Linear solver
                  'quiet': False}         # Quiet flag

    def __init__(self):
        """
        Interior-point non-linear programming solver.
        """
        
        # Init
        OptSolver.__init__(self)
        self.parameters = OptSolverINLP.parameters.copy()
        self.linsolver = None

    def solve(self,problem):
        """
        Solves optimization problem.
        
        Parameters
        ----------
        problem : Object
        """
    
        # Local vars
        norm2 = self.norm2
        norminf = self.norminf
        parameters = self.parameters
        
        # Parameters
        tol = parameters['tol']
        maxiter = parameters['maxiter']
        quiet = parameters['quiet']
        sigma = parameters['sigma']
        eps = parameters['eps']
        eps_cold = parameters['eps_cold']

        # Problem
        problem = cast_problem(problem)
        self.problem = problem
        
        # Linsolver
        self.linsolver = new_linsolver(parameters['linsolver'],'symmetric')

        # Reset
        self.reset()

        # Checks
        if not np.all(problem.l <= problem.u):
            raise OptSolverError_NoInterior(self)

        # Constants
        self.A = problem.A
        self.AT = problem.A.T
        self.b = problem.b
        self.u = problem.u+1e-5*(problem.u-problem.l)+1e-8
        self.l = problem.l-1e-5*(problem.u-problem.l)-1e-8
        self.n = problem.get_num_primal_variables()
        self.m1 = problem.get_num_linear_equality_constraints()
        self.m2 = problem.get_num_nonlinear_equality_constraints()
        self.e = np.ones(self.n)
        self.I = eye(self.n,format='coo')
        self.Omm1 = coo_matrix((self.m1,self.m1))
        self.Omm2 = coo_matrix((self.m2,self.m2))

        # Initial primal
        if problem.x is None:
            self.x = (self.u + self.l)/2.
        else:
            dul = eps*(self.u-self.l)
            self.x = np.maximum(np.minimum(problem.x,self.u-dul),self.l+dul)

        # Initial duals
        if problem.lam is None:
            self.lam = np.zeros(problem.get_num_linear_equality_constraints())
        else:
            self.lam = problem.lam.copy()
        if problem.nu is None:
            self.nu = np.zeros(problem.get_num_nonlinear_equality_constraints())
        else:
            self.nu = problem.nu.copy()
        if problem.mu is None:
            self.mu = np.ones(self.x.size)*eps_cold
        else:
            self.mu = np.maximum(problem.mu,eps)
        if problem.pi is None:
            self.pi = np.ones(self.x.size)*eps_cold
        else:
            self.pi = np.maximum(problem.pi,eps)

        # Init vector
        self.y = np.hstack((self.x,self.lam,self.nu,self.mu,self.pi))

        # Average violation of complementarity slackness
        self.eta_mu = np.dot(self.mu,self.u-self.x)/self.x.size
        self.eta_pi = np.dot(self.pi,self.x-self.l)/self.x.size

        # Objective scaling
        fdata = self.func(self.y)
        self.obj_sca = np.maximum(norminf(problem.gphi)/10.,1.)
        fdata = self.func(self.y)

        # Header
        if not quiet:
            print('\nSolver: INLP')
            print('------------')
                                   
        # Outer
        s = 0.
        self.k = 0
        while True:

            # Average violation of complementarity slackness
            self.eta_mu = np.dot(self.mu,self.u-self.x)/self.x.size
            self.eta_pi = np.dot(self.pi,self.x-self.l)/self.x.size
            
            # Init eval
            fdata = self.func(self.y)
            fmax = norminf(fdata.f)     # KKT residual
            gmax = norminf(fdata.GradF) # Gradient of merit function
            
            # Done
            if fmax < tol and sigma*np.maximum(self.eta_mu,self.eta_pi) < tol:
                self.set_status(self.STATUS_SOLVED)
                self.set_error_msg('')
                return

            # Target
            tau = sigma*norminf(fdata.GradF)
           
            # Header
            if not quiet:
                if self.k > 0:
                    print('')
                print('{0:^3s}'.format('iter'),end=' ')
                print('{0:^9s}'.format('phi'),end=' ')
                print('{0:^9s}'.format('fmax'),end=' ')
                print('{0:^9s}'.format('gmax'),end=' ')
                print('{0:^8s}'.format('cu'),end=' ')
                print('{0:^8s}'.format('cl'),end=' ')
                print('{0:^8s}'.format('alpha'))
 
            # Inner
            while True:
                
                # Eval
                fdata = self.func(self.y)
                fmax = norminf(fdata.f)
                gmax = norminf(fdata.GradF)
                compu = norminf(self.mu*(self.u-self.x))
                compl = norminf(self.pi*(self.x-self.l))
                phi = problem.phi
                
                # Show progress
                if not quiet:
                    print('{0:^3d}'.format(self.k),end=' ')
                    print('{0:^9.2e}'.format(phi),end=' ')
                    print('{0:^9.2e}'.format(fmax),end=' ')
                    print('{0:^9.2e}'.format(gmax),end=' ')
                    print('{0:^8.1e}'.format(compu),end=' ')
                    print('{0:^8.1e}'.format(compl),end=' ')
                    print('{0:^8.1e}'.format(s))
                
                # Done
                if gmax < tau: 
                    break

                # Done 
                if fmax < tol and np.maximum(compu,compl) < tol:
                    break

                # Maxiters
                if self.k >= maxiter:
                    raise OptSolverError_MaxIters(self)
                
                # Search direction
                ux = self.u-self.x
                xl = self.x-self.l
                D1 = spdiags(self.mu/ux,0,self.n,self.n,format='coo')
                D2 = spdiags(self.pi/xl,0,self.n,self.n,format='coo')
                fbar = np.hstack((-fdata.rd+fdata.ru/ux-fdata.rl/xl,fdata.rp1,fdata.rp2))
                Hbar = coo_matrix((np.concatenate((problem.Hphi.data/self.obj_sca,
                                                   problem.H_combined.data,
                                                   D1.data,
                                                   D2.data)),
                                   (np.concatenate((problem.Hphi.row,
                                                    problem.H_combined.row,
                                                    D1.row,
                                                    D2.row)),
                                    np.concatenate((problem.Hphi.col,
                                                    problem.H_combined.col,
                                                    D1.col,
                                                    D2.col)))))
                Jbar = bmat([[Hbar,None,None],
                             [-self.A,self.Omm1,None],
                             [-problem.J,None,self.Omm2]],
                            format='coo')
                try:
                    if not self.linsolver.is_analyzed():
                        self.linsolver.analyze(Jbar)
                    pbar = self.linsolver.factorize_and_solve(Jbar,fbar)
                except RuntimeError:
                    raise OptSolverError_BadLinSystem(self)
                px = pbar[:self.n]
                pmu = (-fdata.ru + self.mu*px)/ux
                ppi = (-fdata.rl - self.pi*px)/xl
                p = np.hstack((pbar,pmu,ppi))

                # Steplength bounds
                indices = px > 0
                s1 = np.min(np.hstack(((self.u-self.x)[indices]/px[indices],np.inf)))
                indices = px < 0
                s2 = np.min(np.hstack(((self.l-self.x)[indices]/px[indices],np.inf)))
                indices = pmu < 0
                s3 = np.min(np.hstack((-self.mu[indices]/pmu[indices],np.inf)))
                indices = ppi < 0
                s4 = np.min(np.hstack((-self.pi[indices]/ppi[indices],np.inf)))
                smax = (1.-eps)*np.min([s1,s2,s3,s4])
                
                # Line search
                s = np.min([smax,1.])
                
                # Update x
                self.y += s*p
                self.k += 1
                self.x,self.lam,self.nu,self.mu,self.pi = self.extract_components(self.y)

                # Check
                try:
                    assert(np.all(self.x < self.u))
                    assert(np.all(self.x > self.l))
                    assert(np.all(self.mu > 0))
                    assert(np.all(self.pi > 0))
                except AssertionError:
                    raise OptSolverError_Infeasibility(self)
        
    def extract_components(self,y):

        n = self.n
        m1 = self.m1
        m2 = self.m2
        
        x = y[:n]
        lam = y[n:n+m1]
        nu = y[n+m1:n+m1+m2]
        mu = y[n+m1+m2:2*n+m1+m2]
        pi = y[2*n+m1+m2:]

        return x,lam,nu,mu,pi
        
    def func(self,y):
        
        fdata = self.fdata
        sigma = self.parameters['sigma']
        prob = self.problem
        obj_sca = self.obj_sca

        x,lam,nu,mu,pi = self.extract_components(y)

        # Eval
        prob.eval(x)
        prob.combine_H(-nu)
        
        ux = self.u-x
        xl = x-self.l

        JT = prob.J.T
        
        rd = prob.gphi/obj_sca-self.AT*lam-JT*nu+mu-pi # dual residual
        rp1 = self.A*x-self.b                          # primal residual 1
        rp2 = prob.f                                   # primal residual 2
        ru = mu*ux-sigma*self.eta_mu*self.e            # residual of perturbed complementarity
        rl = pi*xl-sigma*self.eta_pi*self.e            # residual of perturbed complementarity
        
        Dmu = spdiags(self.mu,0,self.n,self.n)
        Dux = spdiags(ux,0,self.n,self.n)
        Dpi = spdiags(self.pi,0,self.n,self.n)
        Dxl = spdiags(xl,0,self.n,self.n)

        f = np.hstack((rd,rp1,rp2,ru,rl))          # residuals
        H = prob.Hphi/obj_sca + prob.H_combined    # second derivatives
        H = H + H.T - triu(H)
        J = bmat([[H,-self.AT,-JT,self.I,-self.I], # Jacobian or residuals
                  [self.A,None,None,None,None],
                  [prob.J,None,None,None,None],
                  [-Dmu,None,None,Dux,None],
                  [Dpi,None,None,None,Dxl]],
                 format='coo')

        # Save
        fdata.rd = rd
        fdata.rp1 = rp1
        fdata.rp2 = rp2
        fdata.ru = ru
        fdata.rl = rl
        fdata.f = f
        fdata.J = J

        # Merid function
        fdata.F = 0.5*np.dot(f,f) # merit function
        fdata.GradF = J.T*f       # gradient of merit function

        # Return data
        return fdata
