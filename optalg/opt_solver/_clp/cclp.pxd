#****************************************************#
# This file is part of OPTALG.                       #
#                                                    #
# Copyright (c) 2015-2017, Tomas Tinoco De Rubira.   #
#                                                    #
# OPTALG is released under the BSD 2-clause license. #
#****************************************************#

cdef extern from "coin/Clp_C_Interface.h":

    ctypedef void Clp_Simplex
    
    Clp_Simplex* Clp_newModel()
    void Clp_deleteModel(Clp_Simplex* model)
    
    void Clp_loadProblem(Clp_Simplex* model, int numcols, int numrows, int* start, int* index, double* value,
                         double* collb, double* collu, double* obj, double* rowlb, double* rowub)

    int Clp_status(Clp_Simplex* model)
    void Clp_setlogLevel(Clp_Simplex* model, int value)
    int Clp_initialSolve(Clp_Simplex* model)
    
    
