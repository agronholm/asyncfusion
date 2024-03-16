/**
 * This is an io_uring based I/O operations provider.
 *
 * Further optimization ideas:
 * - Kernel thread polling
 * - Register socket descriptors
 * - Use zero-copy send
 * - Use multi-shot operations
 **/

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <liburing.h>
#include <arpa/inet.h>
#include <sys/un.h>
#include <poll.h>
#define Py_LIMITED_API PYTHON_API_VERSION

typedef struct {
    PyObject_HEAD
    struct io_uring ring;
} IoUringObject;

enum RequestType {
    ACCEPT,
    CLOSE,
    CONNECT,
    POLL,
    RECV,
    RECVFROM,
    SEND,
    SENDTO,
    SLEEP
};

struct accept_operation {
    struct sockaddr_storage from_addr;
    socklen_t addrlen;
};

struct connect_operation {
    struct sockaddr_storage to_addr;
};

struct recv_operation {
    char *buf;
};

struct recvfrom_operation {
    int sockfd;
    char *buf;
    size_t buflen;
    int flags;
    struct sockaddr_storage from_addr;
    socklen_t addrlen;
};

struct sendto_operation {
    struct sockaddr_storage to_addr;
};

struct sleep_operation {
    struct __kernel_timespec ts;
    PyObject *result;
};

struct request {
    enum RequestType type;
    PyObject *future;
    union {
        struct accept_operation accept;
        struct connect_operation connect;
        struct recv_operation recv;
        struct recvfrom_operation recvfrom;
        struct sendto_operation sendto;
        struct sleep_operation sleep;
    };
};

static PyObject *FutureType;
static PyObject *future_str_set_result;
static PyObject *future_str_set_exception;
static PyObject *SocketType;

/**
 * Helper functions
 **/

static PyObject *raise_oserror(int error) {
    PyObject *args = Py_BuildValue("is", error, strerror(error));
    PyErr_SetObject(PyExc_OSError, args);
    return NULL;
}

static struct io_uring_sqe *get_new_sqe(struct io_uring *ring, struct request *req) {
    struct io_uring_sqe *sqe = io_uring_get_sqe(ring);
    if (!sqe) {
        int res = io_uring_submit(ring);
        if (res < 0) {
            PyErr_SetFromErrno(PyExc_OSError);
            return NULL;
        }

        sqe = io_uring_get_sqe(ring);
        assert(sqe);
    }

    // Set the request as the SQE's data
    io_uring_sqe_set_data(sqe, req);

    return sqe;
};

static struct request *create_request(
    enum RequestType type,
    struct io_uring *ring,
    struct io_uring_sqe **sqe
) {
    // Allocate the request
    struct request *req = PyMem_Calloc(sizeof(struct request), 1);
    if (!req) {
        PyErr_NoMemory();
        return NULL;
    }

    // Set the request type
    req->type = type;

    // Create a Future
    req->future = PyObject_CallNoArgs(FutureType);
    if (!req->future) {
        PyMem_Free(req);
        return NULL;
    }

    if (sqe) {
        // Create the submission queue entry and set the request as its data
        *sqe = get_new_sqe(ring, req);
        if (!*sqe)
            return NULL;
    }

    return req;
}

static void free_request(struct request *req) {
    Py_DECREF(req->future);
    switch (req->type) {
        case RECV:
            if (req->recv.buf)
                PyMem_Free(req->recv.buf);

            break;
        case RECVFROM:
            if (req->recvfrom.buf)
                PyMem_Free(req->recvfrom.buf);

            break;
        case SLEEP:
            Py_DECREF(req->sleep.result);
            break;
        default:
            break;
    }
    PyMem_Free(req);
}

static int parse_sockaddr(
    PyObject *addr_obj,
    int family,
    struct sockaddr_storage *target_addr,
    socklen_t *target_addr_length
) {
    target_addr->ss_family = family;
    switch (family) {
        case AF_INET:
            // Set up the address structure
            struct sockaddr_in *addr_inet = (struct sockaddr_in *)target_addr;
            *target_addr_length = sizeof(struct sockaddr_in);

            // Unpack the tuple into the C variables
            char *host;
            in_port_t port;
            if (!PyArg_ParseTuple(addr_obj, "etH", "ascii", &host, &port))
                return 0;

            // Set the IP address in the structure
            int ret = inet_pton(AF_INET, host, &addr_inet->sin_addr);
            PyMem_Free(host);
            if (!ret) {
                PyErr_SetString(PyExc_ValueError, "error parsing IP address");
                return 0;
            }

            // Set the port number in the structure
            addr_inet->sin_port = htons(port);
            break;
        case AF_INET6:
            // Set up the address structure
            struct sockaddr_in6 *addr_inet6 = (struct sockaddr_in6 *)target_addr;
            *target_addr_length = sizeof(struct sockaddr_in6);

            // Unpack the tuple into the C variables
            char *host6;
            in_port_t port6;
            if (!PyArg_ParseTuple(
                    addr_obj, "etH|kk", "ascii", &host6, &port6,
                    &addr_inet6->sin6_flowinfo, &addr_inet6->sin6_scope_id
            ))
                return 0;

            // Set the IP address in the structure
            int ret6 = inet_pton(AF_INET6, host6, &addr_inet6->sin6_addr);
            PyMem_Free(host6);
            if (!ret6) {
                PyErr_SetString(PyExc_ValueError, "error parsing IPv6 address");
                return 0;
            }

            // Set the port number in the structure
            addr_inet6->sin6_port = htons(port6);
            break;
        case AF_UNIX:
            // Set up the address structure
            struct sockaddr_un *addr_un = (struct sockaddr_un *)target_addr;
            *target_addr_length = sizeof(struct sockaddr_un);

            // Convert the path to a bytestring if needed
            PyObject *addr_bytestring;
            bool need_deallocate_addr_bytestring;
            if (PyUnicode_Check(addr_obj)) {
                need_deallocate_addr_bytestring = true;
                addr_bytestring = PyUnicode_EncodeFSDefault(addr_obj);
            } else if (PyBytes_Check(addr_obj)) {
                need_deallocate_addr_bytestring = false;
                addr_bytestring = addr_obj;
            } else {
                PyErr_SetString(
                    PyExc_TypeError,
                    "socket path must be either a unicode string or a bytestring"
                );
                return 0;
            }

            // Convert the bytestring into a C character array and length
            char *path;
            Py_ssize_t pathlen;
            if (PyBytes_AsStringAndSize(addr_bytestring, &path, &pathlen) < 0) {
                printf("PyBytes_AsStringAndSize failed\n");
                goto unix_error;
            }

            // Check that the path doesn't exceed the maximum size
            if ((unsigned long)pathlen >= sizeof(addr_un->sun_path)) {
                PyErr_SetString(PyExc_ValueError, "socket path exceeds maximum size");
                goto unix_error;
            }

            // Set the address family and path on the address structure
            strcpy(addr_un->sun_path, path);
            if (need_deallocate_addr_bytestring)
                Py_DECREF(addr_bytestring);

            break;

unix_error:
            if (need_deallocate_addr_bytestring)
                Py_DECREF(addr_bytestring);

            return 0;
        default:
            PyErr_Format(PyExc_ValueError, "unsupported address family: %d", family);
            return 0;
    }
    return 1;
}

static PyObject *build_pyobject_from_sockaddr(struct sockaddr_storage *addr) {
    switch (addr->ss_family) {
        case AF_INET:
            struct sockaddr_in *addr_inet = (struct sockaddr_in *)addr;
            char addr_string[INET_ADDRSTRLEN];
            if (!inet_ntop(AF_INET, &addr_inet->sin_addr, addr_string, sizeof(addr_string))) {
                PyErr_SetFromErrno(PyExc_OSError);
                return NULL;
            }

            return Py_BuildValue("si", addr_string, ntohs(addr_inet->sin_port));
        case AF_INET6:
            struct sockaddr_in6 *addr_inet6 = (struct sockaddr_in6 *)addr;
            char addr6_string[INET6_ADDRSTRLEN];
            if (!inet_ntop(AF_INET6, &addr_inet6->sin6_addr, addr6_string, sizeof(addr6_string))) {
                PyErr_SetFromErrno(PyExc_OSError);
                return NULL;
            }

            return Py_BuildValue(
                "siii", addr6_string, ntohs(addr_inet6->sin6_port), addr_inet6->sin6_flowinfo,
                addr_inet6->sin6_scope_id);
        case AF_UNIX:
            return Py_BuildValue("s", ((struct sockaddr_un *)addr)->sun_path);
        default:
            PyErr_Format(PyExc_ValueError, "invalid address family: %d", addr->ss_family);
            return NULL;
    }
}

static int handle_cqe(struct io_uring_cqe *cqe) {
    // Handle a completion queue event
    PyObject *result = NULL;
    struct request *req = (struct request *)io_uring_cqe_get_data(cqe);

    // Special case SLEEP, as it always sets errno to -62
    if (req->type == SLEEP && cqe->res == -62)
        cqe->res = 0;

    if (cqe->res < 0) {
        result = PyObject_CallFunction(PyExc_OSError, "is", -cqe->res, strerror(-cqe->res));
        if (!result || !PyObject_CallMethodOneArg(req->future, future_str_set_exception, result))
            goto error;
   } else {
        switch (req->type) {
            case RECV:
                result = PyBytes_FromStringAndSize(req->recv.buf, cqe->res);
                break;
            case SEND:
                result = PyLong_FromSsize_t(cqe->res);
                break;
            case SLEEP:
                result = req->sleep.result;
                break;
            case ACCEPT:
                PyObject *addr_object = build_pyobject_from_sockaddr(&req->accept.from_addr);
                if (!addr_object)
                    goto error;

                result = Py_BuildValue("iO", cqe->res, addr_object);
                break;
            case RECVFROM:
                // Got the POLLIN event, so the socket can be read from now
                socklen_t addrlen = sizeof(struct sockaddr_storage);
                ssize_t retval = recvfrom(
                    req->recvfrom.sockfd, req->recvfrom.buf, req->recvfrom.buflen,
                    req->recvfrom.flags, (struct sockaddr *)&req->recvfrom.from_addr, &addrlen
                );
                if (retval < 0) {
                    result = PyObject_CallFunction(PyExc_OSError, "is", errno, strerror(errno));
                    if (!result || !PyObject_CallMethodOneArg(req->future, future_str_set_exception, result))
                        goto error;

                    break;
                }

                addr_object = build_pyobject_from_sockaddr(&req->recvfrom.from_addr);
                if (!addr_object)
                    goto error;

                result = Py_BuildValue("y#O", req->recvfrom.buf, retval, addr_object);
                break;
            default:
                result = Py_None;
        }

        if (!result || !PyObject_CallMethodOneArg(req->future, future_str_set_result, result))
            goto error;
    }

    free_request(req);
    return 1;

error:
    free_request(req);
    return 0;
}

/**
 * IoUringObject methods
 **/

static PyObject *asyncfusion_uring_close(IoUringObject *self) {
    io_uring_queue_exit(&self->ring);
    Py_RETURN_NONE;
}

static PyObject *asyncfusion_uring_init(IoUringObject *self) {
    int ret;

    ret = io_uring_queue_init(100, &self->ring, 0);
    if (ret < 0)
        return PyErr_SetFromErrno(PyExc_OSError);

    Py_RETURN_NONE;
}

static PyObject *asyncfusion_uring_poll(IoUringObject *self, PyObject *args) {
    bool wait;
    if (!PyArg_ParseTuple(args, "p:poll", &wait))
        return NULL;

    // Flush any pending submissions, optionally also waiting for at least one CQE
    int ret;
    if (wait)
        ret = io_uring_submit_and_wait(&self->ring, 1);
    else
        ret = io_uring_submit(&self->ring);

    if (ret < 0)
        return raise_oserror(-ret);

    // Handle all other pending queues (but don't wait for more)
    unsigned head;
    unsigned cqes_seen = 0;
    struct io_uring_cqe *cqe;
    io_uring_for_each_cqe(&self->ring, head, cqe) {
        cqes_seen++;
        if (!handle_cqe(cqe)) {
            io_uring_cq_advance(&self->ring, cqes_seen);
            return NULL;
        }
    }

    io_uring_cq_advance(&self->ring, cqes_seen);
    Py_RETURN_NONE;
}

static PyObject *asyncfusion_uring_sock_accept(IoUringObject *self, PyObject *args) {
    int sockfd;
    if (!PyArg_ParseTuple(args, "i:sock_accept", &sockfd))
        return NULL;

    // Fill in the length of the socket address structure based on the socket's address
    // family
    int family;
    socklen_t optlen = sizeof(family);
    if (getsockopt(sockfd, SOL_SOCKET, SO_DOMAIN, &family, &optlen) < 0) {
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }

    // Create the request and the submission queue entry
    struct io_uring_sqe *sqe;
    struct request *req = create_request(ACCEPT, &self->ring, &sqe);
    if (!req)
        return NULL;

    // Prepare the accept() operation
    req->accept.addrlen = sizeof(struct sockaddr_storage);
    io_uring_prep_accept(
        sqe, sockfd, (struct sockaddr *)&req->accept.from_addr, &req->accept.addrlen,
        SOCK_CLOEXEC
    );

    Py_INCREF(req->future);
    return req->future;
}

static PyObject *asyncfusion_uring_sock_close(IoUringObject *self, PyObject *args) {
    int sockfd;
    if (!PyArg_ParseTuple(args, "i:sock_close", &sockfd))
        return NULL;

    // Create the request and the submission queue entry
    struct io_uring_sqe *sqe;
    struct request *req = create_request(CLOSE, &self->ring, &sqe);
    if (!req)
        return NULL;

    // Prepare the close() operation and attach the future to the SQE
    io_uring_prep_close(sqe, sockfd);

    Py_INCREF(req->future);
    return req->future;
}

static PyObject *asyncfusion_uring_sock_connect(IoUringObject *self, PyObject *args) {
    int sockfd;
    sa_family_t family;
    PyObject *addr;

    if (!PyArg_ParseTuple(args, "iHO:sock_connect", &sockfd, &family, &addr))
        return NULL;

    // Create the request (without a SQE)
    struct request *req = create_request(CONNECT, &self->ring, NULL);
    if (!req)
        return NULL;

    socklen_t addrlen;
    if (!parse_sockaddr(addr, family, &req->connect.to_addr, &addrlen))
        goto error;

    // Create a submission queue entry
    struct io_uring_sqe *sqe = get_new_sqe(&self->ring, req);
    if (!sqe)
        goto error;

    // Prepare the connect() operation
    io_uring_prep_connect(sqe, sockfd, (struct sockaddr *)&req->connect.to_addr, addrlen);

    Py_INCREF(req->future);
    return req->future;

error:
    free_request(req);
    return NULL;
}

static PyObject *asyncfusion_uring_sock_recv(IoUringObject *self, PyObject *args) {
    int sockfd;
    ssize_t length;
    int flags = 0;
    if (!PyArg_ParseTuple(args, "in|i:sock_recv", &sockfd, &length, &flags))
        return NULL;

    // Create the request and submission queue entry
    struct io_uring_sqe *sqe;
    struct request *req = create_request(RECV, &self->ring, &sqe);
    if (!req)
        return NULL;

    // Allocate a buffer for the receive operation
    req->recv.buf = PyMem_Malloc(length);
    if (!req->recv.buf) {
        PyErr_NoMemory();
        free_request(req);
        return NULL;
    }

    // Prepare the recv() operation and attach the future to the SQE
    io_uring_prep_recv(sqe, sockfd, req->recv.buf, length, flags);

    Py_INCREF(req->future);
    return req->future;
}

static PyObject *asyncfusion_uring_sock_recvfrom(IoUringObject *self, PyObject *args) {
    int sockfd;
    ssize_t length;
    int flags = 0;
    if (!PyArg_ParseTuple(args, "in|i:sock_recvfrom", &sockfd, &length, &flags))
        return NULL;

    // Create the request and submission queue entry
    struct io_uring_sqe *sqe;
    struct request *req = create_request(RECVFROM, &self->ring, &sqe);
    if (!req)
        return NULL;

    // Fill in the recvfrom structure
    req->recvfrom.sockfd = sockfd;
    req->recvfrom.buflen = length;
    req->recvfrom.flags = flags;

    // Allocate a buffer for the receive operation
    req->recvfrom.buf = PyMem_Malloc(length);
    if (!req->recvfrom.buf) {
        free_request(req);
        PyErr_NoMemory();
        return NULL;
    }

    // Prepare the poll_add() operation (as there is no recvfrom operation in io_uring
    // at this time) and attach the future to the SQE
    io_uring_prep_poll_add(sqe, sockfd, POLLIN);

    Py_INCREF(req->future);
    return req->future;
}

static PyObject *asyncfusion_uring_sock_send(IoUringObject *self, PyObject *args) {
    int sockfd;
    char *buffer;
    Py_ssize_t length;
    int flags = 0;
    if (!PyArg_ParseTuple(args, "iy#|i:sock_send", &sockfd, &buffer, &length, &flags))
        return NULL;

    // Create the request and the submission queue entry
    struct io_uring_sqe *sqe;
    struct request *req = create_request(SEND, &self->ring, &sqe);
    if (!req)
        return NULL;

    // Prepare the send() operation and attach the future to the SQE
    io_uring_prep_send(sqe, sockfd, buffer, length, flags);

    Py_INCREF(req->future);
    return req->future;
}

static PyObject *asyncfusion_uring_sock_sendto(IoUringObject *self, PyObject *args) {
    int sockfd;
    char *buffer;
    Py_ssize_t length;
    PyObject *addr;
    int flags = 0;
    if (!PyArg_ParseTuple(args, "iy#O|i:sock_sendto", &sockfd, &buffer, &length, &addr, &flags))
        return NULL;

    // Find out the address family
    int family;
    socklen_t optlen = sizeof(family);
    if (getsockopt(sockfd, SOL_SOCKET, SO_DOMAIN, &family, &optlen) < 0) {
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }

    // Create the request and the submission queue entry
    struct io_uring_sqe *sqe;
    struct request *req = create_request(SEND, &self->ring, &sqe);
    if (!req)
        return NULL;

    // Parse the address
    socklen_t addrlen;
    req->sendto.to_addr.ss_family = family;
    if (!parse_sockaddr(addr, family, &req->sendto.to_addr, &addrlen)) {
        free_request(req);
        return NULL;
    }

    // Prepare the sendto() operation and attach the future to the SQE
    io_uring_prep_sendto(
        sqe, sockfd, buffer, length, flags, (struct sockaddr *)&req->sendto.to_addr,
        addrlen
    );

    Py_INCREF(req->future);
    return req->future;
}

static PyObject *asyncfusion_uring_sock_wait_readable(IoUringObject *self, PyObject *args) {
    int sockfd;
    if (!PyArg_ParseTuple(args, "i:sock_wait_readable", &sockfd))
        return NULL;

    // Create the request and the submission queue entry
    struct io_uring_sqe *sqe;
    struct request *req = create_request(POLL, &self->ring, &sqe);
    if (!req)
        return NULL;

    // Prepare the poll_add() operation and attach the future to the SQE
    io_uring_prep_poll_add(sqe, sockfd, POLLIN);

    Py_INCREF(req->future);
    return req->future;
}

static PyObject *asyncfusion_uring_sock_wait_writable(IoUringObject *self, PyObject *args) {
    int sockfd;
    if (!PyArg_ParseTuple(args, "i:sock_wait_writable", &sockfd))
        return NULL;

    // Create the request and the submission queue entry
    struct io_uring_sqe *sqe;
    struct request *req = create_request(POLL, &self->ring, &sqe);
    if (!req)
        return NULL;

    // Prepare the poll_add() operation and attach the future to the SQE
    io_uring_prep_poll_add(sqe, sockfd, POLLOUT);

    Py_INCREF(req->future);
    return req->future;
}

static PyObject *asyncfusion_uring_sleep(IoUringObject *self, PyObject *args) {
    double seconds = 0;
    PyObject *result = Py_None;
    if (!PyArg_ParseTuple(args, "d|O:sleep", &seconds, &result))
        return NULL;

    // Create the request and the submission queue entry
    struct io_uring_sqe *sqe;
    struct request *req = create_request(SLEEP, &self->ring, &sqe);
    if (!req)
        return NULL;

    // Fill in the timeout structure
    req->sleep.ts.tv_sec = (__kernel_time_t)floor(seconds);
    req->sleep.ts.tv_nsec = (long long)((seconds - floor(seconds)) * 1e9);

    // Store the eventual result
    Py_INCREF(result);
    req->sleep.result = result;

    // Prepare the sleep() operation
    io_uring_prep_timeout(sqe, &req->sleep.ts, 0, 0);

    Py_INCREF(req->future);
    return req->future;
}

static PyMethodDef IoUringMethods[] = {
    {"close", (PyCFunction)asyncfusion_uring_close, METH_NOARGS, "Close io_uring"},
    {"init", (PyCFunction)asyncfusion_uring_init, METH_NOARGS, "Initialize io_uring"},
    {"poll", (PyCFunction)asyncfusion_uring_poll, METH_VARARGS, "Poll for io_uring completions"},
    {"sleep", (PyCFunction)asyncfusion_uring_sleep, METH_VARARGS, "Sleep for the specified amount of seconds"},
    {"sock_accept", (PyCFunction)asyncfusion_uring_sock_accept, METH_VARARGS, "Accept an incoming connection"},
    {"sock_close", (PyCFunction)asyncfusion_uring_sock_close, METH_VARARGS, "Close a socket"},
    {"sock_connect", (PyCFunction)asyncfusion_uring_sock_connect, METH_VARARGS, "Connect the given socket to the given address"},
    {"sock_recv", (PyCFunction)asyncfusion_uring_sock_recv, METH_VARARGS, "Receive data from a socket"},
    {"sock_recvfrom", (PyCFunction)asyncfusion_uring_sock_recvfrom, METH_VARARGS, "Receive data and the source address from a socket"},
    {"sock_send", (PyCFunction)asyncfusion_uring_sock_send, METH_VARARGS, "Send data to a socket"},
    {"sock_sendto", (PyCFunction)asyncfusion_uring_sock_sendto, METH_VARARGS, "Send data to the given address through a socket"},
    {"sock_wait_readable", (PyCFunction)asyncfusion_uring_sock_wait_readable, METH_VARARGS, "Wait until a socket has data to read"},
    {"sock_wait_writable", (PyCFunction)asyncfusion_uring_sock_wait_writable, METH_VARARGS, "Wait until a socket can be written to"},
    {NULL, NULL, 0, NULL} // Sentinel
};

static PyTypeObject IoUringType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "io_uring.IoUring",
    .tp_doc = "An io_uring based asynchronous event loop implementation",
    .tp_basicsize = sizeof(IoUringObject),
    .tp_itemsize = 0,
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_new = PyType_GenericNew,
    .tp_methods = IoUringMethods
};

static struct PyModuleDef io_uring_module = {
    PyModuleDef_HEAD_INIT,
    .m_name = "io_uring",
    .m_doc = "io_uring module",
    .m_size = -1,
};

PyMODINIT_FUNC PyInit__io_uring(void) {
    PyObject *m;

    if (PyType_Ready(&IoUringType) < 0)
        return NULL;

    m = PyModule_Create(&io_uring_module);
    if (m == NULL)
        return NULL;

    // Import the asyncfusion._futures module
    PyObject *futures_module = PyImport_ImportModule("asyncfusion._futures");
    if (!futures_module)
        return NULL;

    // Get the Future class
    FutureType = PyObject_GetAttrString(futures_module, "Future");
    Py_DECREF(futures_module);
    if (!FutureType)
        return NULL;

    // Import the socket module
    PyObject *socket_module = PyImport_ImportModule("socket");
    if (!socket_module)
        return NULL;

    // Get the socket class
    SocketType = PyObject_GetAttrString(socket_module, "socket");
    Py_DECREF(socket_module);
    if (!SocketType)
        return NULL;

    // Intern the strings for method names
    future_str_set_result = PyUnicode_InternFromString("set_result");
    future_str_set_exception = PyUnicode_InternFromString("set_exception");

    // Add the IoUring class
    Py_INCREF(&IoUringType);
    if (PyModule_AddObject(m, "IoUring", (PyObject *)&IoUringType) < 0)
        return NULL;

    return m;
}
