
#ifndef __dvdnavsrc_marshal_MARSHAL_H__
#define __dvdnavsrc_marshal_MARSHAL_H__

#include	<glib-object.h>

G_BEGIN_DECLS

/* VOID:VOID (dvdnavsrcmarshal.list:1) */
#define dvdnavsrc_marshal_VOID__VOID	g_cclosure_marshal_VOID__VOID

/* VOID:POINTER (dvdnavsrcmarshal.list:2) */
#define dvdnavsrc_marshal_VOID__POINTER	g_cclosure_marshal_VOID__POINTER

/* VOID:INT (dvdnavsrcmarshal.list:3) */
#define dvdnavsrc_marshal_VOID__INT	g_cclosure_marshal_VOID__INT

/* VOID:INT,INT (dvdnavsrcmarshal.list:4) */
extern void dvdnavsrc_marshal_VOID__INT_INT (GClosure     *closure,
                                             GValue       *return_value,
                                             guint         n_param_values,
                                             const GValue *param_values,
                                             gpointer      invocation_hint,
                                             gpointer      marshal_data);

/* VOID:INT,INT,INT,INT (dvdnavsrcmarshal.list:5) */
extern void dvdnavsrc_marshal_VOID__INT_INT_INT_INT (GClosure     *closure,
                                                     GValue       *return_value,
                                                     guint         n_param_values,
                                                     const GValue *param_values,
                                                     gpointer      invocation_hint,
                                                     gpointer      marshal_data);

/* VOID:INT,INT,UINT,UINT,UINT,UINT,UINT,UINT (dvdnavsrcmarshal.list:6) */
extern void dvdnavsrc_marshal_VOID__INT_INT_UINT_UINT_UINT_UINT_UINT_UINT (GClosure     *closure,
                                                                           GValue       *return_value,
                                                                           guint         n_param_values,
                                                                           const GValue *param_values,
                                                                           gpointer      invocation_hint,
                                                                           gpointer      marshal_data);

G_END_DECLS

#endif /* __dvdnavsrc_marshal_MARSHAL_H__ */

