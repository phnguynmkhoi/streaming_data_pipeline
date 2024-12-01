CREATE OR REPLACE FUNCTION set_status_to_updated()
RETURNS TRIGGER AS $$
BEGIN
    -- Check if the status column needs to be updated
    IF NEW.status IS DISTINCT FROM 'UPDATED' THEN
        NEW.status := 'UPDATED';
    END IF;
    RETURN NEW; -- Return the modified row
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_status_trigger
BEFORE UPDATE ON public.transactions
FOR EACH ROW
EXECUTE FUNCTION set_status_to_updated();

CREATE TRIGGER update_status_trigger
BEFORE UPDATE ON public.shippings
FOR EACH ROW
EXECUTE FUNCTION set_status_to_updated();

CREATE TRIGGER update_status_trigger
BEFORE UPDATE ON public.users
FOR EACH ROW
EXECUTE FUNCTION set_status_to_updated();

CREATE TRIGGER update_status_trigger
BEFORE UPDATE ON public.products
FOR EACH ROW
EXECUTE FUNCTION set_status_to_updated();

CREATE TRIGGER update_status_trigger
BEFORE UPDATE ON public.payments
FOR EACH ROW
EXECUTE FUNCTION set_status_to_updated();